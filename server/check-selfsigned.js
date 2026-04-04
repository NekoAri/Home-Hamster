const s = require('selfsigned');
const p = s.generate(null, { days: 1 });
console.log('Result:', JSON.stringify(p));
