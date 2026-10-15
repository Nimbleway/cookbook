// The shape every sweep run returns: one row per event, plus the leads the run saw but
// couldn't confirm. Passed as developer config on each run, so the model never writes it.
export const SWEEP_OUTPUT_SCHEMA = {
  "type": "object",
  "required": [
    "product",
    "window_start",
    "window_end",
    "events",
    "no_events_found",
    "unverified"
  ],
  "additionalProperties": true,
  "properties": {
    "product": {
      "type": "string",
      "description": "Product name, verbatim from the input."
    },
    "window_start": {
      "type": "string",
      "description": "ISO 8601 date the search window starts."
    },
    "window_end": {
      "type": "string",
      "description": "ISO 8601 date the search window ends."
    },
    "no_events_found": {
      "type": "boolean",
      "description": "true only when events is empty."
    },
    "unverified": {
      "type": "array",
      "items": {
        "type": "string"
      },
      "description": "Leads that could not be confirmed from a cited source."
    },
    "events": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": true,
        "required": [
          "headline",
          "event_type",
          "location",
          "affected_exposures",
          "event_date",
          "status",
          "impact_mechanism",
          "source_url",
          "published_at"
        ],
        "properties": {
          "headline": {
            "type": "string",
            "description": "One-line factual headline for the event."
          },
          "event_type": {
            "type": "string",
            "description": "One of: port_disruption, labor_action, export_control, tariff_or_customs, sanctions, factory_incident, natural_hazard, supplier_distress, route_disruption, material_shortage, other."
          },
          "summary": {
            "type": "string",
            "description": "Two to three sentences: what happened and what is known so far."
          },
          "location": {
            "type": "string",
            "description": "Facility, port, city, or country where the event happens."
          },
          "affected_exposures": {
            "type": "array",
            "items": {
              "type": "string"
            },
            "description": "Exposures from the input that this event touches, copied verbatim."
          },
          "event_date": {
            "type": "string",
            "description": "ISO 8601 date the event happened or takes effect."
          },
          "status": {
            "type": "string",
            "description": "One of: announced, ongoing, escalating, easing, resolved."
          },
          "expected_duration": {
            "type": [
              "string",
              "null"
            ],
            "description": "Stated or reported duration as text, e.g. '2-3 weeks'. null if not reported, never omit."
          },
          "impact_mechanism": {
            "type": "string",
            "description": "One sentence on how the event reaches this product."
          },
          "source_url": {
            "type": "string",
            "description": "URL of the page reporting the event."
          },
          "published_at": {
            "type": "string",
            "description": "ISO 8601 publication date of the cited page."
          }
        }
      }
    }
  }
} as const satisfies Record<string, unknown>;
