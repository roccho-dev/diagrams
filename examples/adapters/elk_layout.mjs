import fs from 'node:fs';
import ELK from 'elkjs/lib/elk.bundled.js';

const [input, output] = process.argv.slice(2);
if (!input || !output) {
  console.error('usage: node elk_layout.mjs model.drawio layout.json');
  process.exit(2);
}
const xml = fs.readFileSync(input, 'utf8');
const objects = [...xml.matchAll(/<object\b([^>]*)>/g)].map(match => match[1]);
const attr = (text, key) => text.match(new RegExp(`${key}="([^"]*)"`))?.[1] ?? '';
const nodes = objects.filter(text => attr(text, 'jsonlType') === 'node').map(text => ({ id: attr(text, 'jsonlId'), width: 132, height: 58 }));
const edges = objects.filter(text => attr(text, 'jsonlType') === 'edge').map(text => ({ id: attr(text, 'jsonlId'), sources: [attr(text, 'semanticSource')], targets: [attr(text, 'semanticTarget')] }));
const elk = new ELK();
const graph = await elk.layout({ id: 'root', layoutOptions: { 'elk.algorithm': 'layered' }, children: nodes, edges });
fs.writeFileSync(output, JSON.stringify({ engine: 'elk.layered', available: true, layoutOnly: true, fallbackUsed: false, nodes: Object.fromEntries((graph.children || []).map(node => [node.id, { x: node.x, y: node.y, w: node.width, h: node.height }])) }, null, 2) + '\n');
