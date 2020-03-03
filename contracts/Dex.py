import smartpy as sp

class Dex(sp.Contract):
    def __init__(self,
                 feeRate: sp.TNat,
                 tokenAddress: sp.TAddress,
                 factoryAddress: sp.TAddress,
                 delegated: sp.TKeyHash):
        self.init(
            feeRate=sp.nat(feeRate),
            tezPool=sp.nat(0),
            tokenPool=sp.nat(0),
            invariant=sp.nat(0),
            totalShares=sp.nat(0),
            tokenAddress=tokenAddress,
            factoryAddress=factoryAddress,
            # sp.TAddress, sp.TNat
            shares=sp.big_map(tkey=sp.TAddress, tvalue=sp.TNat),
            # sp.TAddress, sp.TKeyHash
            candidates=sp.big_map(tkey=sp.TAddress, tvalue=sp.TKeyHash),
            # sp.TKeyHash, sp.TNat
            votes=sp.big_map(tkey=sp.TKeyHash, tvalue=sp.TNat),
            delegated=sp.key_hash(delegated),
            address=sp.set(sp.TAddress)
        )
        self.data.address = sp.to_address(sp.self)

    @sp.entry_point
    def InitializeExchange(self, params):
        token_amount = sp.as_nat(params.token_amount)
        candidate = sp.key_hash(params.candidate)

        sp.verify(self.data.invariant == 0, message="Wrong invariant")
        sp.verify(self.data.totalShares == 0, message="Wrong totalShares")
        sp.verify(((sp.amount > sp.mutez(1)) & (
            sp.amount < sp.tez(500000000))), message="Wrong amount")
        sp.verify(token_amount > sp.nat(10), message="Wrong tokenAmount")

        self.data.tokenPool = token_amount
        self.data.tezPool = sp.mutez(sp.amount)
        self.data.invariant = self.data.tezPool * self.data.tokenPool
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

        sp.verify(tezIn > 0, message="Wrong tezIn")
        sp.verify(minTokensOut > 0, message="Wrong minTokensOut")

        fee = tezIn / self.data.feeRate  # TODO: ????
        newTezPool = sp.local("newTezPool", self.data.tezPool).value + tezIn
        tempTezPool = abs(newTezPool - fee)
        newTokenPool = sp.local(
            "newTokenPool", self.data.invariant).value / tempTezPool
        tokensOut = abs(
            sp.local("tokensOut", self.data.tokenPool).value - newTokenPool)

        sp.verify(tokensOut >= minTokensOut, message="Wrong minTokensOut")
        sp.verify(tokensOut <= self.data.tokenPool, message="Wrong tokenPool")

        self.data.tezPool = newTezPool
        self.data.tokenPool = newTokenPool
        self.data.invariant = newTezPool * newTokenPool
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
        newTezPool = sp.local(
            "newTezPool", self.data.invariant).value / tempTokenPool
        tezOut = abs(
            sp.local("tezOut", self.data.tokenPool).value - newTezPool)

        sp.verify(tezOut >= minTezOut, message="Wrong minTezOut")
        sp.verify(tezOut <= self.data.tezPool, message="Wrong tezPool")

        self.data.tezPool = newTezPool
        self.data.tokenPool = newTokenPool
        self.data.invariant = newTezPool * newTokenPool

        token_contract = sp.contract(
            sp.TRecord(account_from=sp.TAddress,
                       destination=sp.TAddress,
                       value=sp.TNat),
            address=self.data.tokenAddress,
            entry_point="Transfer"
        ).open_some()

        receiver_contract = sp.contract(
            sp.TUnit,
            address=recipient
        ).open_some()

        sp.transfer(sp.record(account_from=buyer,
                              destination=this,
                              value=tokensIn),
                    sp.mutez(0),
                    token_contract)
        sp.send(sp.mutez(tezOut),
                receiver_contract)

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
        newTezPool = sp.local(
            "newTezPool", self.data.invariant).value / tempTokenPool
        tezOut = abs(sp.local("tezOut", self.data.tezPool).value - newTezPool)

        sp.verify(tezOut <= self.data.tezPool, message="Wrong tezPool")

        self.data.tezPool = newTezPool
        self.data.tokenPool = newTokenPool
        self.data.invariant = newTezPool * newTokenPool

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
                               tezIn=sp.mutez(sp.amount),
                               minTokensOut=minTokensOut)

    @sp.entry_point
    def InvestLiquidity(self, params):
        minShares = params.minShares
        candidate = params.candidate

        sp.verify(sp.amount > sp.mutez(0), message="Wrong amount")
        sp.verify(minShares > sp.nat(0), message="Wrong tokenAmount")

        tezPerShare = sp.as_nat(self.data.tezPool / self.data.totalShares)

        sp.verify(sp.amount >= sp.mutez(tezPerShare),
                  message="Wrong tezPerShare")

        sharesPurchased = sp.as_nat(sp.mutez(sp.amount) / tezPerShare)

        sp.verify(sharesPurchased >= minShares,
                  message="Wrong sharesPurchased")

        tokensPerShare = sp.as_nat(self.data.tokenPool / self.data.totalShares)
        tokensRequired = sharesPurchased * tokensPerShare
        share = sp.local("share", self.data.shares.get(sp.sender, 0)).value
        self.data.shares[sp.sender] = share + sharesPurchased
        self.data.tezPool += sp.mutez(sp.amount)
        self.data.tokenPool += tokensRequired
        self.data.invariant = self.data.tezPool * self.data.tokenPool
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
        tezPerShare = sp.nat(self.data.tezPool / self.data.totalShares)
        tokensPerShare = sp.nat(self.data.tokenPool / self.data.totalShares)
        tezDivested = tezPerShare * sharesBurned
        tokensDivested = tokensPerShare * sharesBurned

        sp.verify(tezDivested >= minTez, message="Wrong minTez")
        sp.verify(tokensDivested >= minTokens, message="Wrong minTokens")

        self.data.totalShares -= sharesBurned
        self.data.tezPool -= tezDivested
        self.data.tokenPool -= tokensDivested
        sp.if self.data.totalShares == 0:
            self.data.invariant = 0
        sp.else:
            self.data.invariant = self.data.tezPool * self.data.tokenPool

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

        receiver_contract = sp.contract(
            sp.TUnit,
            address=sp.sender
        ).open_some()

        sp.transfer(sp.record(account_from=self.data.address,
                              destination=sp.sender,
                              value=tokensDivested),
                    sp.mutez(0),
                    token_contract)

        sp.send(sp.mutez(tezDivested), receiver_contract)

        
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
        scenario.h2("Dex contract")
        exchange = Dex(500, fake_token.address,
                       fake_factory.address, admin.public_key_hash)
        scenario += exchange
