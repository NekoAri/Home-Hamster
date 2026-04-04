/**
 * 生成自签名 SSL 证书（含局域网 IP SAN）
 * 使用 node-forge
 */
const forge = require('node-forge');
const fs = require('fs');
const path = require('path');
const os = require('os');

// 获取本机所有内网 IP
function getLocalIPs() {
  const nets = os.networkInterfaces();
  const ips = [];
  for (const name of Object.keys(nets)) {
    for (const net of nets[name]) {
      if (net.family === 'IPv4' && !net.internal) {
        ips.push(net.address);
      }
    }
  }
  return ips;
}

const localIPs = getLocalIPs();
console.log('📍 检测到本机 IP:', localIPs);

// 生成密钥对
console.log('🔐 正在生成密钥对（需要几秒钟）...');
const keys = forge.pki.rsa.generateKeyPair(2048);
const cert = forge.pki.createCertificate();

cert.publicKey = keys.publicKey;
cert.serialNumber = '01';
cert.validity.notBefore = new Date();
cert.validity.notAfter = new Date();
cert.validity.notAfter.setFullYear(cert.validity.notBefore.getFullYear() + 10);

const attrs = [
  { name: 'commonName',       value: 'HomeInventory' },
  { name: 'countryName',      value: 'CN' },
  { name: 'organizationName', value: 'Home Inventory' },
];

cert.setSubject(attrs);
cert.setIssuer(attrs);

// 设置 SAN：包含 localhost 和所有本机 IP
const altNames = [
  { type: 2, value: 'localhost' },
  { type: 7, ip: '127.0.0.1' },
  ...localIPs.map(ip => ({ type: 7, ip })),
];

cert.setExtensions([
  { name: 'basicConstraints', cA: true },
  {
    name: 'keyUsage',
    keyCertSign: true,
    digitalSignature: true,
    nonRepudiation: true,
    keyEncipherment: true,
    dataEncipherment: true,
  },
  {
    name: 'extKeyUsage',
    serverAuth: true,
    clientAuth: true,
  },
  {
    name: 'subjectAltName',
    altNames,
  },
]);

cert.sign(keys.privateKey, forge.md.sha256.create());

// 导出 PEM
const keyPem  = forge.pki.privateKeyToPem(keys.privateKey);
const certPem = forge.pki.certificateToPem(cert);

// 保存到 certs 目录
const certDir = path.join(__dirname, 'certs');
if (!fs.existsSync(certDir)) fs.mkdirSync(certDir, { recursive: true });

fs.writeFileSync(path.join(certDir, 'key.pem'),  keyPem);
fs.writeFileSync(path.join(certDir, 'cert.pem'), certPem);

console.log('');
console.log('✅ SSL 证书生成成功！');
console.log('   私钥：server/certs/key.pem');
console.log('   证书：server/certs/cert.pem');
console.log('');
console.log('📱 HTTPS 访问地址：');
localIPs.forEach(ip => console.log(`   https://${ip}:3443`));
console.log('   https://localhost:3443');
console.log('');
console.log('⚠️  首次访问提示"连接不私密/不安全"属正常现象（自签证书）');
console.log('   iPhone Safari：点击"显示详细内容" → "访问此网站" → "访问"');
console.log('   Mac Safari：点击"显示详细信息" → "仍然访问"');
