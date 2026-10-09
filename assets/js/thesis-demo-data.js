window.THESIS_DEMO_DATA = {
  "problem": "A telematics box can see harsh braking and speeding, but it cannot see why — a driver who brakes hard to avoid a child looks identical to a driver who brakes hard because they were distracted. Adding the camera changes the verdict.",
  "thesis_title": "A Multimodal Driver Behaviour Evaluation System: Combining Telematics, VLMs and LLMs",
  "thesis_repo": "https://github.com/MatthewMBowyer/Essex_MSC_DataScience_Thesis",
  "weights": [
    {
      "label": "Harsh manoeuvres (episode-based)",
      "weight": 0.2,
      "note": "Cornering, braking, acceleration — the leading cause of fleet accidents"
    },
    {
      "label": "Long speeding episodes (>1 event)",
      "weight": 0.18,
      "note": "Sustained speeding suggests deliberate risk-taking"
    },
    {
      "label": "Driver distraction (phone, seatbelt)",
      "weight": 0.13,
      "note": "Phone use and seatbelt non-compliance raise injury severity"
    },
    {
      "label": "Short speeding episodes (single event)",
      "weight": 0.12,
      "note": "Isolated speed events — lower severity than sustained speeding"
    },
    {
      "label": "Fatigue (eye closed, yawn, fatigue)",
      "weight": 0.12,
      "note": "Fatigue-related crashes are disproportionately fatal"
    },
    {
      "label": "Situational risk (headway, lane)",
      "weight": 0.1,
      "note": "Forward-collision and lane-departure indicators"
    },
    {
      "label": "Power violations",
      "weight": 0.1,
      "note": "External battery disconnect — tampering or avoidance"
    },
    {
      "label": "Camera obstruction",
      "weight": 0.05,
      "note": "Monitoring integrity, not a direct driving behaviour"
    }
  ],
  "change_types": [
    {
      "type": "confirmed",
      "note": "The VLM agreed with what the telematics flagged."
    },
    {
      "type": "refined",
      "note": "The VLM agreed AND found additional events — e.g. telematics said v_phone and the VLM also found SEATBELT_D_OFF."
    },
    {
      "type": "new_context_added",
      "note": "The VLM saw context the telematics had no event for."
    },
    {
      "type": "contradicted",
      "note": "The VLM evidence contradicted the flagged event."
    },
    {
      "type": "not_confirmed",
      "note": "The flagged event could not be confirmed from the camera."
    },
    {
      "type": "no_vlm_signal",
      "note": "No VLM signal was available for the clip."
    }
  ],
  "output_schema": {
    "final_monthly_rankings_vlm.csv": [
      "vehicle_id",
      "window_start",
      "ubi_proxy_score_base",
      "ubi_proxy_score_vlm",
      "score_delta",
      "rank_base",
      "rank_vlm",
      "rank_delta",
      "vehicle_behaviour_class_base",
      "vehicle_behaviour_class_vlm",
      "covered_ratio",
      "covered_clips",
      "total_clips"
    ],
    "event_change_audit.csv": [
      "clip",
      "vehicle_id",
      "terminal_event_id",
      "original_event_description",
      "vlm_events_for_pipeline",
      "vlm_change_type",
      "change_action",
      "change_reason",
      "removed_event",
      "added_event",
      "event_changed_flag"
    ]
  },
  "ranking_rows": [
    {
      "vehicle_id": "429570713",
      "base": 0.4143,
      "vlm": 0.3947,
      "delta": -0.0196,
      "rank_base": 166,
      "rank_vlm": 205,
      "rank_delta": -39,
      "covered_ratio": 1.0,
      "covered_clips": 2,
      "total_clips": 2
    },
    {
      "vehicle_id": "456979367",
      "base": 0.4756,
      "vlm": 0.5284,
      "delta": 0.0529,
      "rank_base": 124,
      "rank_vlm": 90,
      "rank_delta": 34,
      "covered_ratio": 0.083,
      "covered_clips": 1,
      "total_clips": 12
    },
    {
      "vehicle_id": "507451763",
      "base": 0.5691,
      "vlm": 0.5231,
      "delta": -0.046,
      "rank_base": 64,
      "rank_vlm": 94,
      "rank_delta": -30,
      "covered_ratio": 0.03,
      "covered_clips": 1,
      "total_clips": 33
    }
  ],
  "scenarios": [
    {
      "id": "city-stopstart",
      "title": "Urban stop-start commute",
      "meta": "Representative example — dense traffic, frequent idling",
      "telematics": {
        "Harsh braking (per 100 km)": "11.4",
        "Harsh acceleration (per 100 km)": "8.9",
        "Average speed (km/h)": "24",
        "Idle fraction": "31%",
        "Cornering events (per 100 km)": "6.2"
      },
      "vlm": "The dashcam frame shows a following distance of roughly one car length in a 40 km/h zone, a pedestrian near the kerb on the left and a wet road surface.",
      "llm": "Repeated braking in heavy traffic with a short following distance and a pedestrian close to the carriageway points to a reactive driving pattern. The principal risk is rear-end collision under braking; a secondary risk is failing to see a crossing pedestrian in wet conditions.",
      "score_base": 62,
      "score_vlm": 68,
      "band": "Elevated",
      "delta_note": "The camera added a pedestrian-near-kerb observation the telematics had no event for, nudging the risk up."
    },
    {
      "id": "highway-steady",
      "title": "Motorway steady cruise",
      "meta": "Representative example — light traffic, consistent speed",
      "telematics": {
        "Harsh braking (per 100 km)": "1.3",
        "Harsh acceleration (per 100 km)": "0.9",
        "Average speed (km/h)": "101",
        "Idle fraction": "4%",
        "Cornering events (per 100 km)": "0.4"
      },
      "vlm": "The dashcam frame shows a long clear lane ahead, a following distance of roughly four car lengths, and dry road under daylight.",
      "llm": "Smooth longitudinal control with a generous following distance and a clear lane indicates a low-risk motorway profile. The main residual exposure is speed-related rather than behavioural.",
      "score_base": 22,
      "score_vlm": 21,
      "band": "Low",
      "delta_note": "The camera confirmed a clean profile and changed nothing material — a confirmed change type."
    },
    {
      "id": "rural-night",
      "title": "Rural road at night",
      "meta": "Representative example — unlit road, poor visibility",
      "telematics": {
        "Harsh braking (per 100 km)": "5.1",
        "Harsh acceleration (per 100 km)": "2.0",
        "Average speed (km/h)": "72",
        "Idle fraction": "2%",
        "Cornering events (per 100 km)": "3.8"
      },
      "vlm": "The dashcam frame is low-light, showing a single unlit carriageway, no marked lane edges and a bend ahead without street lighting.",
      "llm": "Moderate event rates on an unlit road with limited visibility raise the risk from an unforeseen obstacle or an unmarked bend. Night driving compounds the behavioural signal captured by the telematics.",
      "score_base": 50,
      "score_vlm": 54,
      "band": "Moderate",
      "delta_note": "The camera confirmed the low-light conditions and added unmarked-bend context, refining the risk upward."
    }
  ],
  "stages": [
    {
      "id": "telematics",
      "title": "1. Telematics trace",
      "help": "What went in: the raw event stream from the telematics box. What came out: counts of harsh manoeuvres, speeding and fatigue events, aggregated into episodes. What it changed: nothing yet — this is the telematics-only view, the 'base' score."
    },
    {
      "id": "vlm",
      "title": "2. VLM observation",
      "help": "What went in: anonymised dashcam frames (faces blurred by an InsightFace step). What came out: a vision-language model's description of what is actually happening — following distance, pedestrians, lighting, road surface. What it changed: it can confirm, refine, contradict or add to the telematics events."
    },
    {
      "id": "llm",
      "title": "3. LLM risk narrative",
      "help": "What went in: the combined telematics + VLM signal. What came out: a plain-language risk narrative. What it changed: it turns the numbers into a reason a fleet manager can act on."
    },
    {
      "id": "score",
      "title": "4. Risk score (base vs VLM)",
      "help": "What went in: the same scoring weights, applied twice — once to telematics only (base) and once with the camera evidence folded in (VLM). What came out: two scores, their delta, and the driver's rank under each. What it changed: this comparison IS the thesis contribution — you can see the camera move a driver up or down the fleet ranking."
    }
  ]
};
