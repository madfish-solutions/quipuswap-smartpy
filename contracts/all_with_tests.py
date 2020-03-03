import smartpy as sp


class Token(sp.Contract):
    def __init__(self, owner, totalSupply):
        self.init(
            owner=owner,
            totalSupply=sp.as_nat(totalSupply),
            ledger=sp.big_map({
                owner: sp.record(balance=sp.as_nat(totalSupply), allowances={})

            },
                tkey=sp.TAddress,
                tvalue=sp.TRecord(
                    balance=sp.TNat,
                    allowances=sp.TMap(
                        sp.TAddress,
                        sp.TNat
                    )
            )
            )
        )

    def IsAllowed(self, account_from: sp.TAddress, value: sp.TNat) -> sp.TBool:
        allowed = False
        sp.if sp.sender != account_from:
            src = self.data.ledger[account_from]
            allowance_amount = src.allowances[sp.sender]
            allowed = allowance_amount >= value
        sp.else:
            allowed = True
        return allowed

    @sp.entry_point
    def Transfer(self, params):
        account_from = params.account_from
        destination = params.destination
        value = params.value
        sp.if account_from != destination:
            sp.verify(self.IsAllowed(account_from=account_from,
                                     value=value),
                      message="Sender not allowed to spend token from source")
        src = self.data.ledger[account_from]
        sp.verify(value <= src.balance, message="Source balance is too low")
        src.balance = abs(src.balance - value)
        self.data.ledger[account_from] = src
        dst = sp.record(balance=sp.nat(0), allowances=sp.map(
            tkey=sp.TAddress, tvalue=sp.TNat))
        self.data.ledger[destination] = self.data.ledger.get(destination, dst)
        self.data.ledger[destination].balance += value
        sp.if src.allowances.contains(sp.sender):
            allow_value = sp.local(
                "allow_value", src.allowances[sp.sender]).value - value
            src.allowances[sp.sender] = sp.as_nat(allow_value)
        self.data.ledger[account_from] = src

    @sp.entry_point
    def Mint(self, params):
        value = params.value
        sp.verify(sp.sender == self.data.owner,
                  message="You must be the owner of the contract to mint tokens")
        def_val = sp.record(balance=sp.nat(0), allowances=sp.map(
            tkey=sp.TAddress, tvalue=sp.TNat))
        self.data.ledger[self.data.owner] = self.data.ledger.get(
            self.data.owner, def_val)
        self.data.ledger[self.data.owner].balance += value
        self.data.totalSupply = self.data.totalSupply + value

    @sp.entry_point
    def Burn(self, params):
        value = params.value
        sp.verify(sp.sender == self.data.owner,
                  message="You must be the owner of the contract to burn tokens")
        owner_account = sp.record(balance=sp.nat(
            0), allowances=sp.map(tkey=sp.TAddress, tvalue=sp.TNat))
        sp.if self.data.ledger.contains(self.data.owner):
            owner_account = self.data.ledger[self.data.owner]
        sp.verify(value <= owner_account.balance,
                  message="Owner balance is too low")
        owner_account.balance = sp.as_nat(owner_account.balance - value)

        # subtract allowed amounts by value/len(allowances)
        sp.for key in owner_account.allowances.keys():
            owner_account.allowances[key] = sp.as_nat(
                owner_account.allowances[key] - value/sp.len(owner_account.allowances))

        self.data.ledger[self.data.owner] = owner_account
        self.data.totalSupply = sp.as_nat(self.data.totalSupply - value)

    @sp.entry_point
    def Approve(self, params):
        spender = params.spender
        value = params.value
        sp.if value > self.data.ledger[sp.sender].balance:
            value = self.data.ledger[sp.sender].balance
        sp.if sp.sender != spender:
            src = self.data.ledger[sp.sender]
            src.allowances[spender] = value
            self.data.ledger[sp.sender] = src

    @sp.entry_point
    def GetAllowance(self, params):
        owner = params.owner
        spender = params.spender
        contr = params.contr
        src = self.data.ledger[owner]
        dest_allowance = src.allowances[spender]
        sp.transfer(dest_allowance, sp.tez(0), contr)

    @sp.entry_point
    def GetBalance(self, params):
        account_from = params.account_from
        contr = params.contr
        src = self.data.ledger[account_from]
        sp.transfer(src.balance, sp.tez(0), contr)

    @sp.entry_point
    def GetTotalSupply(self, params):
        contr = params.contr
        sp.transfer(self.data.totalSupply, sp.tez(0), contr)


class Factory(sp.Contract):
    def __init__(self):
        self.init(
            tokenList=sp.list(t=sp.TAddress),
            tokenToExchange=sp.big_map(tkey=sp.TAddress, tvalue=sp.TAddress),
            exchangeToToken=sp.big_map(tkey=sp.TAddress, tvalue=sp.TAddress)
        )

    @sp.entry_point
    def LaunchExchange(self, params):
        token = params.token
        exchange = params.exchange
        sp.verify(~(self.data.tokenToExchange.contains(token) |
                    self.data.exchangeToToken.contains(exchange)),
                  message="Exchange launched")
        self.data.tokenList.push(token)
        self.data.tokenToExchange[token] = exchange
        self.data.exchangeToToken[exchange] = token

    @sp.entry_point
    def TokenToExchangeLookup(self, params):
        tokenOutAddress = params.tokenOutAddress
        recepient = params.recepient
        minTokensOut = params.minTokensOut
        exchange = sp.contract(sp.TRecord(recipient=sp.TAddress,
                                          minTokensOut=sp.TNat),
                               address=self.data.tokenToExchange[tokenOutAddress],
                               entry_point="TokenToTokenIn").open_some()
        sp.transfer(sp.record(recipient=recepient,
                              minTokensOut=minTokensOut),
                    sp.amount,
                    exchange)


class Dex(sp.Contract):
    def __init__(self,
                 feeRate: sp.TNat,
                 tokenAddress: sp.TAddress,
                 factoryAddress: sp.TAddress,
                 delegated: sp.TKeyHash):
        self.init(
            feeRate=sp.nat(feeRate),
            tezPool=sp.mutez(0),
            tokenPool=sp.nat(0),
            invariant=sp.mutez(0),
            totalShares=sp.nat(0),
            tokenAddress=tokenAddress,
            factoryAddress=factoryAddress,
            # sp.TAddress, sp.TNat
            shares=sp.big_map(tkey=sp.TAddress, tvalue=sp.TNat),
            # sp.TAddress, sp.TKeyHash
            candidates=sp.big_map(tkey=sp.TAddress, tvalue=sp.TKeyHash),
            # sp.TKeyHash, sp.TNat
            votes=sp.big_map(tkey=sp.TKeyHash, tvalue=sp.TNat),
            delegated=delegated,
            address=tokenAddress
        )
        self.data.address = sp.to_address(sp.self)

    @sp.entry_point
    def InitializeExchange(self, params):
        token_amount = sp.as_nat(params.token_amount)
        candidate = params.candidate

        sp.verify(self.data.invariant == sp.mutez(0), message="Wrong invariant")
        sp.verify(self.data.totalShares == 0, message="Wrong totalShares")
        sp.verify(((sp.amount > sp.mutez(1)) & (
            sp.amount < sp.tez(500000000))), message="Wrong amount")
        sp.verify(token_amount > sp.nat(10), message="Wrong tokenAmount")

        self.data.tokenPool = token_amount
        self.data.tezPool = sp.amount
        self.data.invariant = sp.split_tokens(self.data.tezPool, self.data.tokenPool, sp.nat(1))
        self.data.shares[sp.sender] = sp.nat(1000)
        self.data.totalShares = sp.nat(1000)

        token_contract = sp.contract(
            sp.TRecord(account_from=sp.TAddress,
                       destination=sp.TAddress,
                       value=sp.TNat),
            address=self.data.tokenAddress,
            entry_point="Transfer"
        ).open_some()

        sp.transfer(sp.record(account_from=sp.sender,
                              destination=self.data.address,
                              value=token_amount),
                    sp.mutez(0),
                    token_contract)

        self.data.candidates[sp.sender] = candidate
        self.data.votes[candidate] = sp.as_nat(1000)
        self.data.delegated = candidate

        sp.set_delegate(sp.some(candidate))

    def TezToToken(self,
                   recipient: sp.TAddress,
                   tezIn: sp.TNat,
                   minTokensOut: sp.TNat):
        this = self.data.address

        sp.verify(tezIn > sp.mutez(0), message="Wrong tezIn")
        sp.verify(minTokensOut > 0, message="Wrong minTokensOut")

        fee = sp.fst(sp.ediv(tezIn, self.data.feeRate).open_some())  # TODO: ????
        newTezPool = sp.local("newTezPool", self.data.tezPool).value + tezIn
        tempTezPool = abs(newTezPool - fee)
        newTokenPool = sp.fst(sp.ediv(sp.local(
            "newTokenPool", self.data.invariant).value, tempTezPool).open_some())
        tokensOut = abs(
            sp.local("tokensOut", self.data.tokenPool).value - newTokenPool)

        sp.verify(tokensOut >= minTokensOut, message="Wrong minTokensOut")
        sp.verify(tokensOut <= self.data.tokenPool, message="Wrong tokenPool")

        self.data.tezPool = newTezPool
        self.data.tokenPool = newTokenPool
        self.data.invariant = sp.split_tokens(newTezPool, newTokenPool, sp.nat(1))
        token_contract = sp.contract(
            sp.TRecord(account_from=sp.TAddress,
                       destination=sp.TAddress,
                       value=sp.TNat),
            address=self.data.tokenAddress,
            entry_point="Transfer"
        ).open_some()
        sp.transfer(sp.record(account_from=this,
                              destination=recipient,
                              value=tokensOut),
                    sp.mutez(0),
                    token_contract)

    @sp.entry_point
    def TezToTokenPayment(self, params):
        recipient = params.recipient
        minTokensOut = params.minTokensOut
        self.TezToToken(recipient=recipient,
                        tezIn=sp.amount,
                        minTokensOut=minTokensOut)

    @sp.entry_point
    def TezToTokenSwap(self, params):
        minTokensOut = params.minTokensOut
        self.TezToToken(recipient=sp.sender,
                        tezIn=sp.amount,
                        minTokensOut=minTokensOut)

    def TokenToTez(self,
                   buyer: sp.TAddress,
                   recipient: sp.TAddress,
                   tokensIn: sp.TNat,
                   minTezOut: sp.TNat):
        this = self.data.address

        sp.verify(tokensIn > 0, message="Wrong tokensIn")
        sp.verify(minTezOut > 0, message="Wrong minTezOut")

        fee = tokensIn / self.data.feeRate  # TODO: ????
        newTokenPool = sp.local(
            "newTokenPool", self.data.tokenPool).value + tokensIn
        tempTokenPool = abs(newTokenPool - fee)
        newTezPool = sp.fst(sp.ediv(sp.local(
            "newTezPool", self.data.invariant).value, tempTokenPool).open_some())
        tezOut = abs(
            sp.local("tezOut", self.data.tokenPool).value - newTezPool)

        sp.verify(tezOut >= minTezOut, message="Wrong minTezOut")
        sp.verify(sp.mutez(tezOut) <= self.data.tezPool, message="Wrong tezPool")

        self.data.tezPool = newTezPool
        self.data.tokenPool = newTokenPool
        self.data.invariant = sp.mutez(newTezPool * newTokenPool)

        token_contract = sp.contract(
            sp.TRecord(account_from=sp.TAddress,
                       destination=sp.TAddress,
                       value=sp.TNat),
            address=self.data.tokenAddress,
            entry_point="Transfer"
        ).open_some()


        sp.transfer(sp.record(account_from=buyer,
                              destination=this,
                              value=tokensIn),
                    sp.mutez(0),
                    token_contract)
        sp.send(recipient, sp.mutez(tezOut),)

    @sp.entry_point
    def TokenToTezPayment(self, params):
        recipient = sp.local("recipient", params.recipient).value
        tokensIn = sp.local("tokensIn", params.tokensIn).value
        minTezOut = sp.local("minTokensOut", params.minTezOut).value
        self.TokenToTez(buyer=sp.sender,
                        recipient=recipient,
                        tokensIn=tokensIn,
                        minTezOut=minTezOut)

    @sp.entry_point
    def TokenToTezSwap(self, params):
        tokensIn = sp.local("tokensIn", params.tokensIn).value
        minTezOut = sp.local("minTokensOut", params.minTezOut).value
        self.TokenToTez(buyer=sp.sender,
                        recipient=sp.sender,
                        tokensIn=tokensIn,
                        minTezOut=minTezOut)

    def TokenToTokenOut(self,
                        buyer: sp.TAddress,
                        recipient: sp.TAddress,
                        tokensIn: sp.TNat,
                        minTokensOut: sp.TNat,
                        tokenOutAddress: sp.TAddress):
        this = self.data.address
        sp.verify(tokensIn > 0, message="Wrong tokensIn")
        sp.verify(minTokensOut > 0, message="Wrong minTokensOut")

        fee = tokensIn / self.data.feeRate  # TODO: ????
        newTokenPool = sp.local(
            "newTokenPool", self.data.tokenPool).value + tokensIn
        tempTokenPool = abs(newTokenPool - fee)
        newTezPool = sp.fst(sp.ediv(sp.local(
            "newTezPool", self.data.invariant).value, tempTokenPool).open_some())
        tezOut = abs(sp.local("tezOut", self.data.tezPool).value - newTezPool)

        sp.verify(sp.mutez(tezOut) <= self.data.tezPool, message="Wrong tezPool")

        self.data.tezPool = newTezPool
        self.data.tokenPool = newTokenPool
        self.data.invariant = sp.mutez(newTezPool * newTokenPool)
        token_contract = sp.contract(
            sp.TRecord(account_from=sp.TAddress,
                       destination=sp.TAddress,
                       value=sp.TNat),
            address=self.data.tokenAddress,
            entry_point="Transfer"
        ).open_some()

        factory_contract = sp.contract(
            sp.TRecord(tokenOutAddress=sp.TAddress,
                       recipient=sp.TAddress,
                       minTokensOut=sp.TNat),
            address=self.data.factoryAddress,
            entry_point="TokenToExchangeLookup"
        ).open_some()

        sp.transfer(sp.record(account_from=buyer,
                              destination=this,
                              value=tokensIn),
                    sp.mutez(0),
                    token_contract)

        sp.transfer(sp.record(tokenOutAddress=tokenOutAddress,
                              destination=recipient,
                              value=minTokensOut),
                    sp.mutez(tezOut),
                    factory_contract)

    @sp.entry_point
    def TokenToTokenPayment(self, params):
        recipient = sp.local("recipient", params.recipient).value
        tokensIn = sp.local("tokensIn", params.tokensIn).value
        minTokensOut = sp.local("minTokensOut", params.minTokensOut).value
        tokenOutAddress = sp.local(
            "tokenOutAddress", params.tokenOutAddress).value
        self.TokenToTokenOut(
            buyer=sp.sender,
            recipient=recipient,
            tokensIn=tokensIn,
            minTokensOut=minTokensOut,
            tokenOutAddress=tokenOutAddress)

    @sp.entry_point
    def TokenToTokenSwap(self, params):
        tokensIn = sp.local("tokensIn", params.tokensIn).value
        minTokensOut = sp.local("minTokensOut", params.minTokensOut).value
        tokenOutAddress = sp.local(
            "tokenOutAddress", params.tokenOutAddress).value
        self.TokenToTokenOut(
            buyer=sp.sender,
            recipient=sp.sender,
            tokensIn=tokensIn,
            minTokensOut=minTokensOut,
            tokenOutAddress=tokenOutAddress)

    @sp.entry_point
    def TokenToTokenIn(self, params):
        recipient = sp.local("recipient", params.recipient).value
        minTokensOut = sp.local("minTokensOut", params.minTokensOut).value
        sp.verify(sp.sender == self.data.factoryAddress,
                  message="Wrong minTezOut")
        return self.TezToToken(recipient=recipient,
                               tezIn=sp.amount,
                               minTokensOut=minTokensOut)

    @sp.entry_point
    def InvestLiquidity(self, params):
        minShares = params.minShares
        candidate = params.candidate

        sp.verify(sp.amount > sp.mutez(0), message="Wrong amount")
        sp.verify(minShares > sp.nat(0), message="Wrong tokenAmount")

        tezPerShare = sp.split_tokens(self.data.tezPool, sp.nat(1), self.data.totalShares)

        sp.verify(sp.amount >= tezPerShare,
                  message="Wrong tezPerShare")

        sharesPurchased = sp.fst(sp.ediv(sp.amount, tezPerShare).open_some())

        sp.verify(sharesPurchased >= minShares,
                  message="Wrong sharesPurchased")

        tokensPerShare = self.data.tokenPool / self.data.totalShares
        tokensRequired = sharesPurchased * tokensPerShare
        share = sp.local("share", self.data.shares.get(sp.sender, 0)).value
        self.data.shares[sp.sender] = share + sharesPurchased
        self.data.tezPool += sp.amount
        self.data.tokenPool += tokensRequired
        self.data.invariant = sp.split_tokens(self.data.tezPool, self.data.tokenPool, sp.nat(1))
        self.data.totalShares += sharesPurchased
        sp.if self.data.candidates.contains(sp.sender):
            prevVotes = self.data.votes.get(self.data.candidates[sp.sender], 0)
            self.data.votes[self.data.candidates[sp.sender]] = abs(
                prevVotes - share)

        self.data.candidates[sp.sender] = candidate
        prevVotes = self.data.votes.get(candidate, 0)
        newVotes = prevVotes + share + sharesPurchased
        self.data.votes[candidate] = newVotes

        token_contract = sp.contract(
            sp.TRecord(account_from=sp.TAddress,
                       destination=sp.TAddress,
                       value=sp.TNat),
            address=self.data.tokenAddress,
            entry_point="Transfer"
        ).open_some()

        sp.transfer(sp.record(account_from=sp.sender,
                              destination=self.data.address,
                              value=tokensRequired),
                    sp.mutez(0),
                    token_contract)

        mainCandidateVotes = self.data.votes.get(self.data.delegated, 0)
        sp.if mainCandidateVotes <= newVotes:
            self.data.delegated = candidate
            sp.set_delegate(sp.some(candidate))

    @sp.entry_point
    def DivestLiquidity(self, params):
        sharesBurned = params.sharesBurned
        minTez = params.minTez
        minTokens = params.minTokens
        sp.verify(sharesBurned > 0, message="Wrong sharesBurned")
        share = sp.local("share", self.data.shares.get(sp.sender, 0)).value
        sp.verify(sharesBurned > share, message="Sender shares are too low")
        self.data.shares[sp.sender] = abs(share - sharesBurned)
        tezPerShare = sp.split_tokens(self.data.tezPool, sp.nat(1), self.data.totalShares)
        tokensPerShare = sp.nat(self.data.tokenPool / self.data.totalShares)
        tezDivested = sp.split_tokens(tezPerShare, sharesBurned, sp.nat(1))
        tokensDivested = tokensPerShare * sharesBurned

        sp.verify(tezDivested >= minTez, message="Wrong minTez")
        sp.verify(tokensDivested >= minTokens, message="Wrong minTokens")

        self.data.totalShares -= sharesBurned
        self.data.tezPool -= tezDivested
        self.data.tokenPool -= tokensDivested
        sp.if self.data.totalShares == 0:
            self.data.invariant = sp.mutez(0)
        sp.else:
            self.data.invariant = sp.split_tokens(self.data.tezPool, self.data.tokenPool, sp.nat(1))

        sp.if self.data.candidates.contains(sp.sender):
            prevVotes = self.data.votes.get(self.data.candidates[sp.sender], 0)
            self.data.votes[self.data.candidates[sp.sender]] = abs(
                prevVotes - sharesBurned)

        token_contract = sp.contract(
            sp.TRecord(account_from=sp.TAddress,
                       destination=sp.TAddress,
                       value=sp.TNat),
            address=self.data.tokenAddress,
            entry_point="Transfer"
        ).open_some()

        sp.transfer(sp.record(account_from=self.data.address,
                              destination=sp.sender,
                              value=tokensDivested),
                    sp.mutez(0),
                    token_contract)

        sp.send(sp.sender, tezDivested)
# Tests
    @sp.add_test(name="QuipuSwap")
    def test():
        scenario = sp.test_scenario()
        scenario.table_of_contents()

        # define test users
        admin = sp.test_account("Admin")
        alice = sp.test_account("Alice")
        bob = sp.test_account("Bob")

        fake_token = sp.test_account("Token")
        fake_factory = sp.test_account("Factory")
        fake_exchange = sp.test_account("Exchange")

        # define a contract

        scenario.p("We start with accounts:")
        scenario.show([admin, alice, bob, fake_token,
                       fake_factory, fake_exchange])

        # show its representation
        scenario.h2("Token contract")
        token = Token(admin.address, 100)
        scenario += token

        scenario.h3("Mint")
        scenario.p("Mint 20")

        scenario += token.Mint(value=20).run(sender=admin)

        scenario.h3("Transfer")

        scenario.p("Transfer to alice 5")
        scenario += token.Transfer(account_from=admin.address,
                                   destination=alice.address, value=5).run(sender=admin)

        scenario.p("Transfer to bob 5")
        scenario += token.Transfer(account_from=admin.address,
                                   destination=bob.address, value=5).run(sender=admin)

        scenario.h3("Approve to spend")

        scenario.p("Approve Bob to spend 10 from Admin")
        scenario += token.Approve(spender=bob.address,
                                  value=10).run(sender=admin)

        scenario.p("Transfer to Alice 5 from Admin by Bob")
        scenario += token.Transfer(account_from=admin.address,
                                   destination=alice.address, value=5).run(sender=bob)

        scenario.p("Approve Alice to spend 10 from Bob")
        scenario += token.Approve(spender=alice.address,
                                  value=10).run(sender=bob)

        scenario.p("Transfer to Admin 5 from Bob by Alice")
        scenario += token.Transfer(account_from=bob.address,
                                   destination=admin.address, value=5).run(sender=alice)

        scenario.h3("Burn")
        scenario.p("Burn 5")
        scenario += token.Burn(value=5).run(sender=admin)

        scenario.simulation(token)

        # show its representation
        scenario.h2("Factory contract")
        factory = Factory()
        scenario += factory

        scenario.h3("Launch Exchange with random addr")

        scenario += factory.LaunchExchange(token=fake_token.address,
                                           exchange=fake_exchange.address).run(sender=admin)

        scenario.h3("Launch another time")
        scenario += factory.LaunchExchange(token=fake_token.address,
                                           exchange=fake_exchange.address).run(sender=admin, valid=False)

        # show its representation
        scenario.h2("Dex contract")
        exchange = Dex(500, fake_token.address,
                       fake_factory.address, admin.public_key_hash)
        scenario += exchange
