import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export", // fully static build served by nginx; no Node runtime on the server
  trailingSlash: true, // emit /route/index.html for clean static serving
};

export default nextConfig;
