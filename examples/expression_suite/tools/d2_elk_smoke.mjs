import ELK from 'elkjs/lib/elk.bundled.js';
import fs from 'node:fs';
import path from 'node:path';

const root = process.argv[2] || 'generated/expression-suite';
const samplesDir = path.join(root, 'samples');
const outDir = path.join(root, 'proof');
fs.mkdirSync(outDir, { recursive: true });
const results = [];
for (const sample of fs.readdirSync(samplesDir).filter(name => /^\d/.test(name)).sort()) {
  const model = fs.readFileSync(path.join(samplesDir, sample, 'model.drawio'), 'utf8');
  const proof = JSON.parse(fs.readFileSync(path.join(samplesDir, sample, 'proof.json'), 'utf8'));
  const modelNodes = [...model.matchAll(/jsonlType="node"/g)].length;
  const modelEdges = [...model.matchAll(/jsonlType="edge"/g)].length;
  const counts = proof.d2SemanticCounts || {};
  results.push({ sample, ok: counts.modelNodes === modelNodes && counts.modelEdges === modelEdges && counts.semanticNodeParity === true && counts.semanticEdgeParity === true && counts.adapterIdsUnique === true, modelNodes, modelEdges });
}
const elk = new ELK();
let elkSmoke;
try {
  const value = await elk.layout({ id:'root', layoutOptions:{'elk.algorithm':'layered'}, children:[{id:'a',width:80,height:40},{id:'b',width:80,height:40}], edges:[{id:'e',sources:['a'],targets:['b']}] });
  elkSmoke={ok:true,width:value.width,height:value.height};
} catch (error) { elkSmoke={ok:false,error:String(error?.message || error)}; }
const report={schema:'D2ElkSmoke.v4',authority:'events.jsonl',soleGeneratedCurrentState:'mxGraphModel',generatedIsAuthority:false,results,elkSmoke};
fs.writeFileSync(path.join(outDir,'d2-elk-smoke.json'),JSON.stringify(report,null,2)+'\n');
process.exit(results.every(item=>item.ok)&&elkSmoke.ok?0:1);
