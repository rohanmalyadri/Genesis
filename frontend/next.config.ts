import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone", // small self-contained server for Docker / Render
  skipTrailingSlashRedirect: true, // the API's routes end with "/" and the proxy must keep it
};

export default nextConfig;
