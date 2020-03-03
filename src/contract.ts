import { StoreType, TezosNodeWriter, TezosParameterFormat, setLogLevel } from 'conseiljs';
import { initAccount } from './account';

setLogLevel('debug');

const tezosNode = '';

async function deployContract() {
    initAccount();
    const contract = ;
    const storage = '{"string": "Sample"}';

    const result = await TezosNodeWriter.sendContractOriginationOperation(tezosNode, keystore, 0, undefined, 100000, '', 1000, 100000, contract, storage, TezosParameterFormat.Micheline);
    console.log(`Injected operation group id ${result.operationGroupID}`);
}
