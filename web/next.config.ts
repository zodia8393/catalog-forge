import type { NextConfig } from "next";

const isGitHubPages = process.env.GITHUB_PAGES === "true";

const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  basePath: isGitHubPages ? "/catalog-forge" : "",
  assetPrefix: isGitHubPages ? "/catalog-forge/" : undefined,
};

export default nextConfig;
