import { ImageResponse } from 'next/og';
import { NextRequest } from 'next/server';

export const runtime = 'edge';

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const ticker = searchParams.get('ticker')?.toUpperCase() || 'TICKER';
    const companyName = searchParams.get('company') || `${ticker} Corporation`;
    const epsActual = searchParams.get('eps');
    const epsEst = searchParams.get('epsEst');
    const epsBeat = searchParams.get('epsBeat');
    const revActual = searchParams.get('rev');
    const revBeat = searchParams.get('revBeat');
    const sentiment = searchParams.get('sentiment') || 'neutral';

    const sentimentColor =
      sentiment === 'bullish' ? '#4ade80' :
      sentiment === 'bearish' ? '#f87171' :
      '#facc15';

    const sentimentLabel =
      sentiment === 'bullish' ? 'BULLISH' :
      sentiment === 'bearish' ? 'BEARISH' :
      'NEUTRAL';

    const epsBeatBool = epsBeat === 'true';
    const revBeatBool = revBeat === 'true';

    return new ImageResponse(
      (
        <div
          style={{
            width: '100%',
            height: '100%',
            display: 'flex',
            flexDirection: 'column',
            background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)',
            padding: '48px 56px',
            fontFamily: 'system-ui, -apple-system, sans-serif',
          }}
        >
          {/* Header: branding + sentiment badge */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '36px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div
                style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '8px',
                  background: 'linear-gradient(135deg, #3b82f6, #1d4ed8)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '18px',
                  color: 'white',
                  fontWeight: 'bold',
                }}
              >
                ↗
              </div>
              <span style={{ color: '#f1f5f9', fontSize: '22px', fontWeight: 'bold' }}>EarningsIQ</span>
            </div>
            <div
              style={{
                background: sentiment === 'bullish' ? 'rgba(74,222,128,0.15)' : sentiment === 'bearish' ? 'rgba(248,113,113,0.15)' : 'rgba(250,204,21,0.15)',
                border: `1.5px solid ${sentimentColor}`,
                borderRadius: '20px',
                padding: '6px 18px',
                color: sentimentColor,
                fontSize: '14px',
                fontWeight: 'bold',
                letterSpacing: '0.08em',
              }}
            >
              {sentimentLabel}
            </div>
          </div>

          {/* Ticker + company */}
          <div style={{ display: 'flex', flexDirection: 'column', marginBottom: '40px' }}>
            <span style={{ color: '#f1f5f9', fontSize: '72px', fontWeight: 'bold', lineHeight: 1, letterSpacing: '-0.02em', fontFamily: 'monospace' }}>
              {ticker}
            </span>
            <span style={{ color: '#94a3b8', fontSize: '24px', marginTop: '8px' }}>{companyName}</span>
          </div>

          {/* EPS + Revenue metrics */}
          <div style={{ display: 'flex', gap: '24px' }}>
            {epsActual && (
              <div
                style={{
                  flex: 1,
                  background: 'rgba(255,255,255,0.04)',
                  borderRadius: '12px',
                  border: '1px solid rgba(255,255,255,0.08)',
                  padding: '24px 28px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '8px',
                }}
              >
                <span style={{ color: '#64748b', fontSize: '13px', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.06em' }}>EPS</span>
                <span style={{ color: '#f1f5f9', fontSize: '38px', fontWeight: 'bold' }}>
                  ${parseFloat(epsActual).toFixed(2)}
                </span>
                {epsEst && (
                  <span style={{ color: '#64748b', fontSize: '14px' }}>
                    Est. ${parseFloat(epsEst).toFixed(2)}
                  </span>
                )}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    background: epsBeatBool ? 'rgba(74,222,128,0.15)' : 'rgba(248,113,113,0.15)',
                    borderRadius: '8px',
                    padding: '4px 10px',
                    width: 'fit-content',
                  }}
                >
                  <span style={{ color: epsBeatBool ? '#4ade80' : '#f87171', fontSize: '13px', fontWeight: 'bold' }}>
                    {epsBeatBool ? '✓ BEAT' : '✗ MISS'}
                  </span>
                </div>
              </div>
            )}

            {revActual && (
              <div
                style={{
                  flex: 1,
                  background: 'rgba(255,255,255,0.04)',
                  borderRadius: '12px',
                  border: '1px solid rgba(255,255,255,0.08)',
                  padding: '24px 28px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '8px',
                }}
              >
                <span style={{ color: '#64748b', fontSize: '13px', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Revenue</span>
                <span style={{ color: '#f1f5f9', fontSize: '38px', fontWeight: 'bold' }}>
                  ${parseFloat(revActual).toFixed(1)}B
                </span>
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    background: revBeatBool ? 'rgba(74,222,128,0.15)' : 'rgba(248,113,113,0.15)',
                    borderRadius: '8px',
                    padding: '4px 10px',
                    width: 'fit-content',
                  }}
                >
                  <span style={{ color: revBeatBool ? '#4ade80' : '#f87171', fontSize: '13px', fontWeight: 'bold' }}>
                    {revBeatBool ? '✓ BEAT' : '✗ MISS'}
                  </span>
                </div>
              </div>
            )}
          </div>

          {/* Footer */}
          <div style={{ marginTop: 'auto', color: '#334155', fontSize: '13px' }}>
            earningsiq.app · Not financial advice
          </div>
        </div>
      ),
      {
        width: 1200,
        height: 630,
      }
    );
  } catch (e) {
    console.error(e);
    return new Response('Failed to generate OG image', { status: 500 });
  }
}
