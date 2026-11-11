import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {createReviewStore} from './review-store.mjs';
import {validateReviewEvent} from './contract.mjs';
const [file,root]=process.argv.slice(2);if(!file)throw Error('Usage: node pool/import-reviews.mjs input.jsonl [private-ledger-root]');
const bytes=await readFile(file);if(bytes.length>16*1024*1024)throw Error('Import exceeds the pilot budget');
const events=bytes.toString('utf8').split('\n').filter(line=>line.trim()).map(JSON.parse);if(events.length>5000)throw Error('Import exceeds the event budget');
const store=createReviewStore(root?{root}:{});
// Validate the full input before making any writes. An interrupted valid import can
// be repeated: event IDs are immutable and duplicate delivery is idempotent.
for(const event of events)validateReviewEvent(event,await store.pool(event.poolId));
let created=0;for(const event of events)if((await store.append(event)).created)created++;
console.log(JSON.stringify({events:events.length,created,alreadyPresent:events.length-created,sourceSha256:createHash('sha256').update(bytes).digest('hex'),ledger:store.root}));
