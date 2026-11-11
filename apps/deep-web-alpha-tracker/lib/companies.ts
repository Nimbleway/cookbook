import type { Company } from './types';

/** The fund's tech watchlist: names under consideration, grouped by the sleeve that covers them. */
export const COMPANIES: Company[] = [
  { ticker: 'NVDA', name: 'NVIDIA', domain: 'nvidia.com', sector: 'Semis' },
  { ticker: 'AMD', name: 'Advanced Micro Devices', domain: 'amd.com', sector: 'Semis' },
  { ticker: 'AVGO', name: 'Broadcom', domain: 'broadcom.com', sector: 'Semis' },
  { ticker: 'TSM', name: 'Taiwan Semiconductor', domain: 'tsmc.com', sector: 'Semis' },
  { ticker: 'INTC', name: 'Intel', domain: 'intel.com', sector: 'Semis' },
  { ticker: 'MU', name: 'Micron Technology', domain: 'micron.com', sector: 'Semis' },
  { ticker: 'ARM', name: 'Arm Holdings', domain: 'arm.com', sector: 'Semis' },
  { ticker: 'MRVL', name: 'Marvell Technology', domain: 'marvell.com', sector: 'Semis' },
  { ticker: 'CRDO', name: 'Credo Technology', domain: 'credosemi.com', sector: 'Semis' },
  { ticker: 'ALAB', name: 'Astera Labs', domain: 'asteralabs.com', sector: 'Semis' },

  { ticker: 'SMCI', name: 'Super Micro Computer', domain: 'supermicro.com', sector: 'AI infrastructure' },
  { ticker: 'VRT', name: 'Vertiv', domain: 'vertiv.com', sector: 'AI infrastructure' },
  { ticker: 'ANET', name: 'Arista Networks', domain: 'arista.com', sector: 'AI infrastructure' },
  { ticker: 'DELL', name: 'Dell Technologies', domain: 'dell.com', sector: 'AI infrastructure' },
  { ticker: 'CRWV', name: 'CoreWeave', domain: 'coreweave.com', sector: 'AI infrastructure' },
  { ticker: 'NBIS', name: 'Nebius Group', domain: 'nebius.com', sector: 'AI infrastructure' },
  { ticker: 'ORCL', name: 'Oracle', domain: 'oracle.com', sector: 'AI infrastructure' },

  { ticker: 'MSFT', name: 'Microsoft', domain: 'microsoft.com', sector: 'Cloud & data' },
  { ticker: 'GOOGL', name: 'Alphabet', domain: 'abc.xyz', sector: 'Cloud & data' },
  { ticker: 'AMZN', name: 'Amazon', domain: 'amazon.com', sector: 'Cloud & data' },
  { ticker: 'SNOW', name: 'Snowflake', domain: 'snowflake.com', sector: 'Cloud & data' },
  { ticker: 'MDB', name: 'MongoDB', domain: 'mongodb.com', sector: 'Cloud & data' },
  { ticker: 'DDOG', name: 'Datadog', domain: 'datadoghq.com', sector: 'Cloud & data' },
  { ticker: 'NET', name: 'Cloudflare', domain: 'cloudflare.com', sector: 'Cloud & data' },

  { ticker: 'CRWD', name: 'CrowdStrike', domain: 'crowdstrike.com', sector: 'Security' },
  { ticker: 'ZS', name: 'Zscaler', domain: 'zscaler.com', sector: 'Security' },
  { ticker: 'PANW', name: 'Palo Alto Networks', domain: 'paloaltonetworks.com', sector: 'Security' },
  { ticker: 'S', name: 'SentinelOne', domain: 'sentinelone.com', sector: 'Security' },
  { ticker: 'OKTA', name: 'Okta', domain: 'okta.com', sector: 'Security' },

  { ticker: 'PLTR', name: 'Palantir Technologies', domain: 'palantir.com', sector: 'AI software' },
  { ticker: 'AI', name: 'C3.ai', domain: 'c3.ai', sector: 'AI software' },
  { ticker: 'PATH', name: 'UiPath', domain: 'uipath.com', sector: 'AI software' },
  { ticker: 'NOW', name: 'ServiceNow', domain: 'servicenow.com', sector: 'AI software' },
  { ticker: 'CRM', name: 'Salesforce', domain: 'salesforce.com', sector: 'AI software' },
  { ticker: 'HUBS', name: 'HubSpot', domain: 'hubspot.com', sector: 'AI software' },
  { ticker: 'TEAM', name: 'Atlassian', domain: 'atlassian.com', sector: 'AI software' },
  { ticker: 'GTLB', name: 'GitLab', domain: 'gitlab.com', sector: 'AI software' },
  { ticker: 'FIG', name: 'Figma', domain: 'figma.com', sector: 'AI software' },
  { ticker: 'TEM', name: 'Tempus AI', domain: 'tempus.com', sector: 'AI software' },

  { ticker: 'META', name: 'Meta Platforms', domain: 'meta.com', sector: 'Consumer internet' },
  { ticker: 'SHOP', name: 'Shopify', domain: 'shopify.com', sector: 'Consumer internet' },
  { ticker: 'APP', name: 'AppLovin', domain: 'applovin.com', sector: 'Consumer internet' },
  { ticker: 'TTD', name: 'The Trade Desk', domain: 'thetradedesk.com', sector: 'Consumer internet' },
  { ticker: 'RBLX', name: 'Roblox', domain: 'roblox.com', sector: 'Consumer internet' },
  { ticker: 'DUOL', name: 'Duolingo', domain: 'duolingo.com', sector: 'Consumer internet' },
  { ticker: 'RDDT', name: 'Reddit', domain: 'redditinc.com', sector: 'Consumer internet' },

  { ticker: 'RKLB', name: 'Rocket Lab', domain: 'rocketlabusa.com', sector: 'Space & defense tech' },
  { ticker: 'ASTS', name: 'AST SpaceMobile', domain: 'ast-science.com', sector: 'Space & defense tech' },
  { ticker: 'KTOS', name: 'Kratos Defense & Security', domain: 'kratosdefense.com', sector: 'Space & defense tech' },
  { ticker: 'IONQ', name: 'IonQ', domain: 'ionq.com', sector: 'Space & defense tech' },
];

export const SECTORS = [...new Set(COMPANIES.map((c) => c.sector))];
