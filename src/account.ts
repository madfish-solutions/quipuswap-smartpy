import { TezosWalletUtil } from 'conseiljs';

import { TezosNodeWriter, StoreType } from 'conseiljs';

const faucetAccount = {
  "mnemonic": [
    "enjoy",
    "fix",
    "grape",
    "extend",
    "skate",
    "obey",
    "anxiety",
    "produce",
    "crew",
    "tail",
    "decide",
    "visit",
    "life",
    "when",
    "scene"
  ],
  "secret": "fbf4d27cec7d40726fbbae08dee3f8246f7a1862",
  "amount": "23085403086",
  "pkh": "tz1eh5JFx29MDWppkGSRNxgwmn3Z8dzGaRDD",
  "password": "Y81yXW31cJ",
  "email": "vdofkmaj.pniyxlmm@tezos.example.org"
}

const tezosNode = '';

async function initAccount() {
    const keystore = await TezosWalletUtil.unlockFundraiserIdentity(faucetAccount.mnemonic.join(' '), faucetAccount.email, faucetAccount.password, faucetAccount.pkh);
    console.log(`public key: ${keystore.publicKey}`);
    console.log(`secret key: ${keystore.privateKey}`);
    return keystore;
}

async function activateAccount(tezosNode, keystore) {
    const result = await TezosNodeWriter.sendIdentityActivationOperation(tezosNode, keystore, '0a09075426ab2658814c1faf101f53e5209a62f5');
    console.log(`Injected operation group id ${result.operationGroupID}`)
}


async function revealAccount(tezosNode, keystore) {

    const result = await TezosNodeWriter.sendKeyRevealOperation(tezosNode, keystore);
    console.log(`Injected operation group id ${result.operationGroupID}`);
}

async function sendTransaction(tezosNode, keystore, to, amount) {
    const result = await TezosNodeWriter.sendTransactionOperation(tezosNode, keystore, to, amount, 1500, '');
    console.log(`Injected operation group id ${result.operationGroupID}`);
}

async function delegateAccount(tezosNode, keystore, to, amount) {
    const keystore = {
        publicKey: 'edpkvQtuhdZQmjdjVfaY9Kf4hHfrRJYugaJErkCGvV3ER1S7XWsrrj',
        privateKey: 'edskRgu8wHxjwayvnmpLDDijzD3VZDoAH7ZLqJWuG4zg7LbxmSWZWhtkSyM5Uby41rGfsBGk4iPKWHSDniFyCRv3j7YFCknyHH',
        publicKeyHash: 'tz1QSHaKpTFhgHLbqinyYRjxD5sLcbfbzhxy',
        seed: '',
        storeType: StoreType.Fundraiser
    };

    const result = await TezosNodeWriter.sendDelegationOperation(tezosNode, keystore, keystore.publicKeyHash, to, amount);
    console.log(`Injected operation group id ${result.operationGroupID}`);
}




initAccount().then(keystore => {
    Promise
        .all([
            activateAccount(tezosNode, keystore)
        ])
        .then
});

export {
    initAccount,
    activateAccount,
    delegateAccount,
    sendTransaction,
    revealAccount
}