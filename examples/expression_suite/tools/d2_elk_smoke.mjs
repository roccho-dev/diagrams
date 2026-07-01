import ELK from 'elkjs/lib/elk.bundled.js';
import fs from 'node:fs';
import path from 'node:path';

const root = process.argv[2] || 'generated/expression-suite';
const samplesDir = path.join(root, 'samples');
const outDir = path.join(root, 'proof');
fs.mkdirSync(outDir, { recursive: true });

function structuralD2Counts(d2Text) {
  let nodeDecls = 0;
  let edgeDecls = 0;
  const seenIds = new Set();
  let collision = false;
  for (const line of d2Text.split(/\r?\n/)) {
    const raw = line.trim();
    if (!raw || raw.startsWith('#')) continue;
    if (raw.includes('->')) {
      edgeDecls += 1;
    } else if (raw.endsWith('{') && !raw.startsWith('classes')) {
      nodeDecls += 1;
      const adapterId = raw.slice(0, -1).trim().replace(/:$/, '').trim();
      if (seenIds.has(adapterId)) collision = true;
      seenIds.add(adapterId);
    }
  }
  return { nodeDecls, edgeDecls, adapterIdsUnique: !collision && seenIds.size === nodeDecls };
}

const results = [];
for (const s of fs.readdirSync(samplesDir).filter(x => /^\d/.test(x)).sort()) {
  const d2File = path.join(samplesDir, s, 'compiled.d2');
  const dvmFile = path.join(samplesDir, s, 'dvm.json');
  const proofFile = path.join(samplesDir, s, 'proof.json');
  const d2Text = fs.readFileSync(d2File, 'utf8');
  const dvm = JSON.parse(fs.readFileSync(dvmFile, 'utf8'));
  const proof = JSON.parse(fs.readFileSync(proofFile, 'utf8'));
  const structural = structuralD2Counts(d2Text);
  const proofCounts = proof.d2SemanticCounts || {};
  const nodeParity = structural.nodeDecls === dvm.nodes.length && proofCounts.d2NodeDecls === dvm.nodes.length && proofCounts.semanticNodeParity === true;
  const edgeParity = structural.edgeDecls === dvm.edges.length && proofCounts.d2EdgeDecls === dvm.edges.length && proofCounts.semanticEdgeParity === true;
  const adapterIdsUnique = structural.adapterIdsUnique === true && proofCounts.adapterIdsUnique === true;
  results.push({
    sample: s,
    ok: nodeParity && edgeParity && adapterIdsUnique,
    dvmNodes: dvm.nodes.length,
    dvmEdges: dvm.edges.length,
    structuralD2NodeDecls: structural.nodeDecls,
    structuralD2EdgeDecls: structural.edgeDecls,
    nodeParity,
    edgeParity,
    adapterIdsUnique,
  });
}

const elk = new ELK();
let elkSmoke = { ok: false };
try {
  const r = await elk.layout({
    id: 'root',
    layoutOptions: { 'elk.algorithm': 'layered' },
    children: [{id:'a',width:80,height:40},{id:'b',width:80,height:40}],
    edges: [{id:'e',sources:['a'],targets:['b']}],
  });
  elkSmoke = { ok: true, width: r.width, height: r.height };
} catch(e) {
  elkSmoke = { ok: false, error: String(e?.message || e) };
}

const report = {
  schema: 'D2ElkSmoke.v3',
  mode: 'structural-d2-parity-plus-elk-runtime',
  authority: 'events.jsonl',
  generatedIsAuthority: false,
  note: '@terrastruct/d2 WASM render is intentionally not required by this semantic gate; compiled.d2 parity is checked structurally and ELK runtime is smoke-tested.',
  results,
  elkSmoke,
};
fs.writeFileSync(path.join(outDir, 'd2-elk-smoke.json'), JSON.stringify(report, null, 2));
process.exit((results.every(r => r.ok) && elkSmoke.ok) ? 0 : 1);
