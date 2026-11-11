/** The Acme Mail demo pricing page, with the Growth price read from Blob by `acme.ts`. */
export function renderAcmePage(growth: number): string {
  const plans = [
    { emails: "10,000", features: ["Email API", "SMTP relay", "7-day logs"], name: "Starter", price: 10 },
    { emails: "50,000", features: ["Email API", "SMTP relay", "30-day logs", "Webhooks"], name: "Growth", price: growth },
    {
      emails: "250,000",
      features: ["Email API", "SMTP relay", "90-day logs", "Webhooks", "Dedicated IP"],
      name: "Scale",
      price: 90,
    },
  ];

  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Acme Mail pricing (demo page, not a real company)</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 860px; margin: 40px auto; padding: 0 16px; color: #111; background: #fff; }
  .banner { background: #edc602; padding: 10px 14px; border-radius: 6px; font-weight: 600; }
  .plans { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-top: 24px; }
  .plan { border: 1px solid #ddd; border-radius: 8px; padding: 16px; }
  .price { font-size: 28px; font-weight: 700; }
</style>
</head>
<body>
<p class="banner">Demo page for the Nimble &times; eve pricing brief cookbook. Acme Mail is not a real company.</p>
<h1>Acme Mail pricing</h1>
<p>Simple monthly plans for transactional email. Billed monthly.</p>
<div class="plans">
${plans
  .map(
    (p) => `  <section class="plan">
    <h2>${p.name}</h2>
    <p class="price">$${p.price}/month</p>
    <p>${p.emails} emails per month</p>
    <ul>${p.features.map((f) => `<li>${f}</li>`).join("")}</ul>
  </section>`
  )
  .join("\n")}
</div>
</body>
</html>
`;
}
