import type { NextConfig } from "next";

// `output: 'standalone'` is required by our Docker image (Dockerfile.frontend
// copies from .next/standalone) but conflicts with AWS Amplify's managed SSR
// compute. Docker sets BUILD_STANDALONE=true; Amplify builds leave it unset.
const nextConfig: NextConfig = {
  ...(process.env.BUILD_STANDALONE === "true" ? { output: "standalone" as const } : {}),

  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "*.s3.amazonaws.com",
        pathname: "/**",
      },
    ],
  },
};

export default nextConfig;
