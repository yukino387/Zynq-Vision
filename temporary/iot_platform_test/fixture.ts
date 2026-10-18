import sharp from "../../apps/server/node_modules/sharp/lib/index.js";
async function main() {
  await sharp(
    Buffer.from(
      '<svg width="416" height="416"><rect width="416" height="416" fill="#aab3a3"/><text x="25" y="60" font-size="19" fill="#244e3c">SIMULATED MOBILE FIXTURE</text><path d="M100 120 L130 200 L110 300" stroke="#244e3c" fill="none" stroke-width="5"/></svg>',
    ),
  )
    .jpeg()
    .toFile("temporary/iot_platform_test/SIMULATED-mobile-fixture.jpg");
}
void main();
