import smartpy as sp


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
        scenario.h2("Factory contract")
        factory = Factory()
        scenario += factory

        scenario.h3("Launch Exchange with random addr")

        scenario += factory.LaunchExchange(token=fake_token.address,
                                           exchange=fake_exchange.address).run(sender=admin)

        scenario.h3("Launch another time")
        scenario += factory.LaunchExchange(token=fake_token.address,
                                           exchange=fake_exchange.address).run(sender=admin, valid=False)
