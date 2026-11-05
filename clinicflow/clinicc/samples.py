SAMPLES = {
    "Cardiac triage (demo)": """// Cardiac triage protocol
let age = 67;
let bp_sys = 165;
let bp_dia = 98;
let hr = 112;
let spo2 = 91;
let temp = 38.9;

let map = (bp_sys + 2 * bp_dia) / 3;

if bp_sys > 140 and bp_dia > 90 then {
    alert "Hypertension detected";
    order "ECG";
    order "ECG";
    if hr > 100 then {
        order "Troponin panel";
    }
}

if map > 110 then {
    alert "Elevated mean arterial pressure";
}

if spo2 < 94 then {
    alert "Low oxygen saturation";
    order "Chest X-ray";
}

if temp >= 38.0 then {
    prescribe "Paracetamol" 500 mg;
} else {
    alert "No fever";
}

let unused_score = 2 * 3 + 4;

if 1 > 2 then {
    order "This is never ordered";
}
""",
    "Diabetes follow-up": """// Diabetes follow-up protocol
let weight = 72;
let glucose = 245;
let hba1c = 8.4;
let insulin_dose = weight * 0.5 / 2;

if glucose > 180 or hba1c >= 8 then {
    alert "Poor glycaemic control";
    order "Renal function test";
    order "Renal function test";
    prescribe "Insulin" insulin_dose units;
} else {
    alert "Glycaemic control acceptable";
}

if not (glucose < 70) then {
    order "Eye screening referral";
}
""",
    "Broken program (see errors)": """// Try fixing these one at a time
let glucose = 250
if glucose > 180 then {
    prescribe "Insulin" 500 units;
}
order ECG;
if missing_value > 3 then {
    alert "x";
}
let spo2 = 140;
prescribe "Paracetamol" 9000 mg;
""",
}
