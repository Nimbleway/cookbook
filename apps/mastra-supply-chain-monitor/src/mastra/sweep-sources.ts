// Where the sweep agent may search. The allow list is a hard whitelist: the agent searches
// only these domains. Order sets priority. Passed as developer config on each run.
export const SWEEP_SOURCES = {
  "allow": [
    {
      "title": "Wires and business news",
      "domains": [
        "reuters.com",
        "www.reuters.com",
        "apnews.com",
        "www.apnews.com",
        "cnbc.com",
        "www.cnbc.com",
        "asia.nikkei.com",
        "scmp.com",
        "www.scmp.com",
        "focustaiwan.tw"
      ],
      "order": 0
    },
    {
      "title": "Supply chain and freight trade press",
      "domains": [
        "supplychaindive.com",
        "www.supplychaindive.com",
        "freightwaves.com",
        "www.freightwaves.com",
        "theloadstar.com",
        "www.theloadstar.com",
        "splash247.com",
        "gcaptain.com",
        "www.gcaptain.com",
        "maritime-executive.com",
        "www.maritime-executive.com",
        "joc.com",
        "www.joc.com"
      ],
      "order": 1
    },
    {
      "title": "Electronics and semiconductor trade press",
      "domains": [
        "digitimes.com",
        "www.digitimes.com",
        "trendforce.com",
        "www.trendforce.com",
        "eetimes.com",
        "www.eetimes.com",
        "tomshardware.com",
        "www.tomshardware.com"
      ],
      "order": 2
    },
    {
      "title": "Official trade and customs notices",
      "domains": [
        "federalregister.gov",
        "www.federalregister.gov",
        "bis.gov",
        "www.bis.gov",
        "bis.doc.gov",
        "www.bis.doc.gov",
        "ustr.gov",
        "www.ustr.gov",
        "cbp.gov",
        "www.cbp.gov",
        "english.mofcom.gov.cn",
        "policy.trade.ec.europa.eu",
        "wto.org",
        "www.wto.org"
      ],
      "order": 3
    },
    {
      "title": "Ports and carrier advisories",
      "domains": [
        "portoflosangeles.org",
        "www.portoflosangeles.org",
        "polb.com",
        "www.polb.com",
        "maersk.com",
        "www.maersk.com",
        "hapag-lloyd.com",
        "www.hapag-lloyd.com"
      ],
      "order": 4
    },
    {
      "title": "Natural hazard alerts",
      "domains": [
        "gdacs.org",
        "www.gdacs.org",
        "earthquake.usgs.gov",
        "cwa.gov.tw",
        "www.cwa.gov.tw"
      ],
      "order": 5
    }
  ]
};
