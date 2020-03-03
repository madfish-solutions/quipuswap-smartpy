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
