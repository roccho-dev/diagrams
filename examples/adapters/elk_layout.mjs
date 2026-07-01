import fs from 'node:fs';
import ELK from 'elkjs/lib/elk.bundled.js';

const input = process.argv[2];
const output = process.argv[3];
if (!input || !output) {
  console.error('usage: node elk_layout.mjs dvm.json layout.json');
  process.exit(2);
}
const dvm = JSON.parse(fs.readFileSync(input, 'utf8'));
const children = (dvm.nodes || []).map(n => ({ id: n.id, width: 132, height: 58 }));
const edges = (dvm.edges || []).map(e => ({ id: e.id, sources: [e.source], targets: [e.target] }));
const elk = new ELK();
try {
  const graph = {
    id: 'root',
    layoutOptions: {
      'elk.algorithm': 'layered',
      'elk.direction': 'RIGHT',
      'elk.spacing.nodeNode': '42',
      'elk.layered.spacing.nodeNodeBetweenLayers': '70'
    },
    children,
    edges
  };
  const result = await elk.layout(graph);
  const nodes = {};
  for (const c of result.children || []) nodes[c.id] = { x: Math.round((c.x || 0) + 48), y: Math.round((c.y || 0) + 88), w: c.width || 132, h: c.height || 58 };
  fs.writeFileSync(output, JSON.stringify({ engine: 'elkjs', available: true, layoutOnly: true, nodes, raw: result }, null, 2));
} catch (e) {
  fs.writeFileSync(output, JSON.stringify({ engine: 'elkjs', available: false, error: String(e?.message || e), nodes: {} }, null, 2));
  process.exit(1);
}
