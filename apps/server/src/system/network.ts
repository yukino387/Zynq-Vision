import { networkInterfaces } from "node:os";

export function serverAddresses(
  port: number,
  interfaces = networkInterfaces(),
) {
  const wireless = /wlan|wi-?fi|wireless|无线/i;
  const virtual =
    /vpn|radmin|tailscale|docker|wsl|vethernet|virtual|vmware|蓝牙|bluetooth|^wg\d|^tun\d|^tap\d/i;
  return Object.entries(interfaces)
    .flatMap(([interfaceName, addresses]) =>
      (addresses ?? [])
        .filter((entry) => entry.family === "IPv4" && !entry.internal)
        .map((entry) => ({
          interfaceName,
          address: entry.address,
          url: `http://${entry.address}:${port}`,
          mobile:
            !entry.address.startsWith("169.254.") &&
            !virtual.test(interfaceName),
        })),
    )
    .sort(
      (a, b) =>
        Number(b.mobile) - Number(a.mobile) ||
        Number(wireless.test(b.interfaceName)) -
          Number(wireless.test(a.interfaceName)),
    );
}

export function mobileServerUrl(value: string) {
  try {
    const url = new URL(value);
    return (
      /^https?:$/.test(url.protocol) &&
      !url.username &&
      !url.password &&
      url.pathname === "/" &&
      !url.search &&
      !url.hash &&
      !/^(localhost|.*\.localhost|127\..*|0\..*|\[::1\]|\[::\])$/i.test(
        url.hostname,
      )
    );
  } catch {
    return false;
  }
}
