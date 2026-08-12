#!/usr/bin/env python3
"""
ERJOR citation analysis - reproducible thematic & methodological coding.

Input : Web of Science / JCR "citable items" export (.xlsx)
Output: labelled dataset + summary tables

Coding is deterministic and rule-based: the same title always yields the same
label, and every assignment records the rule that produced it.
"""

import re
import unicodedata
import pandas as pd

# ---------------------------------------------------------------------------
# 1. Text normalisation
# ---------------------------------------------------------------------------
# The WoS export contains HTML sub/sup tags and mojibake for Greek letters
# (alpha -> 慣, beta -> 棺). Normalise before matching.

MOJIBAKE = {
    "慣": "alpha",
    "棺": "beta",
    "款": "gamma",
    "婁": "mu",
}


def normalise(text: str) -> str:
    if not isinstance(text, str):
        return ""
    t = text
    for bad, good in MOJIBAKE.items():
        t = t.replace(bad, good)
    t = re.sub(r"<[^>]+>", "", t)          # strip <sub>, <SUP> etc.
    t = unicodedata.normalize("NFKD", t)
    t = t.replace("\u2010", "-").replace("\u2011", "-").replace("\u2013", "-")
    t = re.sub(r"\s+", " ", t)
    return t.lower().strip()


# ---------------------------------------------------------------------------
# 2. Theme codebook
# ---------------------------------------------------------------------------
# Ordered most-specific to most-general. Each theme is a list of regex patterns.
# A paper scores 1 point per distinct pattern matched; the highest-scoring theme
# wins, with ties broken by position in this list (earlier = more specific).

THEMES = [
    ("Congress/Assembly Reports", [
        r"\bers international congress\b",
        r"^highlights from\b",
        r"\bhighlights from the\b.*\bassembly\b",
    ]),
    ("Cystic Fibrosis", [
        r"\bcystic fibrosis\b", r"\bcftr\b", r"\bcf-related\b",
        r"\bmodulator\b", r"\belexacaftor\b", r"\bivacaftor\b", r"\blumacaftor\b",
    ]),
    ("Primary Ciliary Dyskinesia", [
        r"\bprimary ciliary dyskinesia\b", r"\bpcd\b",
        r"\bmucociliary clearance\b", r"\bnasal nitric oxide\b",
    ]),
    ("Bronchiectasis", [
        r"\bbronchiectasis\b", r"\bchronic suppurative lung disease\b",
        r"\bairway clearance\b",
    ]),
    ("NTM", [
        r"\bnontuberculous mycobacteri\w*\b", r"\bnon-tuberculous mycobacteri\w*\b",
        r"\bntm\b", r"\bmycobacterial burden\b", r"\bmycobacteriosis\b",
    ]),
    ("COVID-19", [
        r"\bcovid\b", r"\bcovid-19\b", r"\bsars-cov-2\b", r"\bsars-cov\b",
        r"\blong covid\b", r"\bpandemic\b", r"\bcoronavirus\b",
    ]),
    ("Tuberculosis", [
        r"\btuberculosis\b", r"\btb\b", r"\bmycobacterium tuberculosis\b",
        r"\bbedaquiline\b", r"\brifampicin\b", r"\bmultidrug-resistant\b",
        r"\blatent tuberculosis\b",
    ]),
    ("Oncology / Lung Cancer", [
        r"\blung cancer\b", r"\bnsclc\b", r"\bnonsmall cell\b", r"\bnon-small cell\b",
        r"\badenocarcinoma\b", r"\bmesothelioma\b", r"\bthoracic cancer\w*\b",
        r"\bthoracic oncology\b", r"\bpulmonary nodule\w*\b", r"\btumour\w*\b",
        r"\bimmune checkpoint inhibitor\w*\b", r"\blung cancer screening\b",
        r"\bmediastinal lesion\w*\b",
    ]),
    ("Pulmonary Hypertension / Vascular", [
        r"\bpulmonary hypertension\b", r"\bpulmonary arterial hypertension\b",
        r"\bpah\b", r"\bcteph\b", r"\bchronic thromboembolic\b",
        r"\bpulmonary embolism\b", r"\bpulmonary endarterectomy\b",
        r"\bright ventric\w*\b", r"\bpulmonary vascular\b",
        r"\bballoon pulmonary angioplasty\b", r"\bselexipag\b",
        r"\bvenous thromboembolism\b", r"\bpulmonary arterial\b",
    ]),
    ("ILD / Pulmonary Fibrosis", [
        r"\binterstitial lung disease\w*\b", r"\bild\b", r"\bipf\b",
        r"\bidiopathic pulmonary fibrosis\b", r"\bpulmonary fibrosis\b",
        r"\bfibrosing\b", r"\bfibrotic\b", r"\bnintedanib\b", r"\bpirfenidone\b",
        r"\bhypersensitivity pneumonitis\b", r"\binterstitial lung abnormalit\w*\b",
        r"\bpleuroparenchymal fibroelastosis\b", r"\bantifibrotic\w*\b",
        r"\borganising pneumonia\b", r"\busual interstitial pneumonia\b",
    ]),
    ("Sarcoidosis", [
        r"\bsarcoidosis\b",
    ]),
    ("Alpha-1 Antitrypsin Deficiency", [
        r"\balpha\W?1\W?antitrypsin\b", r"\balpha1-antitrypsin\b",
        r"\bpi\*zz\b", r"\bpi\*sz\b",
    ]),
    ("Sleep", [
        r"\bsleep apnoea\b", r"\bsleep apnea\b", r"\bosa\b", r"\bcpap\b",
        r"\bpositive airway pressure\b", r"\bsleep-disordered breathing\b",
        r"\bapnoea-hypopnoea\b", r"\bsleep\b", r"\bservo-ventilation\b",
    ]),
    ("Cough", [
        r"\bcough\b", r"\bantitussive\b", r"\bcough reflex\b",
    ]),
    ("Asthma", [
        r"\basthma\b", r"\basthmatic\w*\b", r"\bmepolizumab\b", r"\bbenralizumab\b",
        r"\bdupilumab\b", r"\bomalizumab\b", r"\btezepelumab\b", r"\bbiologic\w*\b",
        r"\beosinophilic\b", r"\btype 2 inflammation\b", r"\bsaba\b",
        r"\bshort-acting beta\b", r"\bbronchial thermoplasty\b",
    ]),
    ("COPD", [
        r"\bcopd\b", r"\bchronic obstructive pulmonary disease\b",
        r"\bemphysema\b", r"\bexacerbation\w* of copd\b",
        r"\blung volume reduction\b", r"\bendobronchial valve\w*\b",
        r"\bairflow obstruction\b", r"\bchronic bronchitis\b",
    ]),
    ("Pleural Disease", [
        r"\bpleural\b", r"\bpleuritis\b", r"\bempyema\b", r"\bchylothorax\b",
        r"\bpleural effusion\w*\b", r"\bchest tube\b",
    ]),
    ("Transplantation", [
        r"\blung transplant\w*\b", r"\btransplantation\b",
        r"\ballograft\b", r"\bbronchiolitis obliterans\b",
    ]),
    ("Critical Care / ARDS / Ventilation", [
        r"\bards\b", r"\bacute respiratory distress syndrome\b",
        r"\bmechanically ventilated\b", r"\bmechanical ventilation\b",
        r"\bintensive care\b", r"\bicu\b", r"\bnoninvasive ventilation\b",
        r"\bventilator-associated\b", r"\bprone position\w*\b",
        r"\brespiratory failure\b", r"\bhelmet\b", r"\bventilator\b",
    ]),
    ("Paediatrics / Neonatal", [
        r"\bchildren\b", r"\bchildhood\b", r"\bpaediatric\w*\b", r"\bpediatric\w*\b",
        r"\binfan\w*\b", r"\bneonat\w*\b", r"\bschoolchildren\b",
        r"\bbronchopulmonary dysplasia\b", r"\badolescent\w*\b", r"\bearly-life\b",
    ]),
    ("Respiratory Infection (other)", [
        r"\bpneumonia\b", r"\brespiratory syncytial virus\b", r"\brsv\b",
        r"\binfluenza\b", r"\bpneumococcal\b", r"\bvaccin\w*\b",
        r"\brespiratory tract infection\w*\b", r"\bmicrobiome\b", r"\bmicrobiota\b",
        r"\bpseudomonas\b", r"\bmrsa\b", r"\brhinovirus\b", r"\bhiv\b",
        r"\bfungal\b", r"\bantibiotic\w*\b", r"\bazithromycin\b",
    ]),
    ("Breathlessness / Dyspnoea", [
        r"\bbreathlessness\b", r"\bdyspnoea\b", r"\bdyspnea\b",
        r"\bmmrc\b", r"\bmedical research council scale\b",
    ]),
    ("Pulmonary Rehabilitation / Physical Activity", [
        r"\bpulmonary rehabilitation\b", r"\brehabilitation\b",
        r"\bphysical activity\b", r"\bexercise capacity\b", r"\bexercise training\b",
        r"\b6-min walk\b", r"\bsit-to-stand\b", r"\bsedentary\b",
        r"\binspiratory muscle training\b", r"\bphysiotherap\w*\b",
    ]),
    ("Smoking / Tobacco / Vaping", [
        r"\bsmoking\b", r"\bsmoker\w*\b", r"\btobacco\b", r"\be-cigarette\w*\b",
        r"\belectronic cigarette\w*\b", r"\bvaping\b", r"\biqos\b",
        r"\bcannabis\b", r"\bevali\b",
    ]),
    ("Lung Function / Physiology", [
        r"\blung function\b", r"\bspirometry\b", r"\bspirometric\b",
        r"\boscillometry\b", r"\breference equation\w*\b", r"\bfev\b",
        r"\bforced expiratory volume\b", r"\bforced vital capacity\b",
        r"\bdiffusing capacity\b", r"\bsmall airway\w*\b", r"\bplethysmograph\w*\b",
        r"\bcapnograph\w*\b", r"\bgas exchange\b", r"\bairway resistance\b",
        r"\blung volumes\b", r"\bbronchodilator respons\w*\b",
        r"\bglobal lung function initiative\b", r"\bbreathing pattern\b",
        r"\bexhaled nitric oxide\b",
    ]),
    ("Basic / Translational Science", [
        r"\bin vitro\b", r"\bmouse\b", r"\bmice\b", r"\bmurine\b", r"\bswine\b",
        r"\bepithelial cell\w*\b", r"\bmacrophage\w*\b", r"\bneutrophil\w*\b",
        r"\borganoid\w*\b", r"\bgene expression\b", r"\bgenome-wide\b",
        r"\bproteome\b", r"\bmetabolome\b", r"\bmultiomics\b", r"\bmetabolomic\w*\b",
        r"\bdna methylation\b", r"\bsingle-nucleotide polymorphism\w*\b",
        r"\bmendelian randomisation\b", r"\bglycocalyx\b", r"\binterleukin\b",
        r"\bautophagy\b", r"\bmir\d+\b", r"\bgene signature\b",
        r"\bendothelial-to-mesenchymal\b", r"\bepithelial-mesenchymal\b",
        r"\bimmunophenotyp\w*\b", r"\bbiomarker\w*\b", r"\bgenetic\b",
    ]),
    ("Breath Analysis / Exhaled Biomarkers", [
        r"\bexhaled breath\b", r"\bbreath analysis\b", r"\bvolatile organic compound\w*\b",
        r"\bvolatile metabolite\w*\b", r"\bion-mobility spectrometry\b",
        r"\bmass spectrometry breath\b", r"\bbreath octane\b", r"\bexhaled air\b",
    ]),
    ("Neuromuscular / Chest Wall", [
        r"\bneuromuscular\b", r"\bamyotrophic lateral sclerosis\b", r"\bmotor neuron\w*\b",
        r"\bmuscular dystrophy\b", r"\bdiaphragm\w*\b", r"\bhypoventilation\b",
        r"\bquadriceps\b", r"\brespiratory muscle\w*\b",
    ]),
    ("Airway Physiology / Mechanisms", [
        r"\bairway epitheli\w*\b", r"\bairway hydration\b", r"\blaryngeal\b",
        r"\bbronchoscop\w*\b", r"\bbronchoalveolar lavage\b", r"\bairway pathology\b",
        r"\bhuman bronchi\b", r"\bmucus\b", r"\baerosol\b", r"\binhaler\w*\b",
        r"\bdrug delivery\b", r"\bairway disease\b",
    ]),
    ("Primary Care / Healthcare Delivery", [
        r"\bprimary care\b", r"\bhealthcare pathway\w*\b", r"\bcare pathway\w*\b",
        r"\btelemedicine\b", r"\btelemonitoring\b", r"\bteleheath\b",
        r"\btelerehabilitation\b", r"\bdigital health\b", r"\bremote monitoring\b",
        r"\bhealth service\w*\b", r"\bquality indicator\w*\b", r"\bcost-effective\w*\b",
        r"\bhealthcare utilisation\b", r"\bmultidisciplinary care\b",
        r"\bshared decision-making\b", r"\bself-management\b", r"\bregistr\w*\b",
        r"\bcarbon footprint\b", r"\badherence\b",
    ]),
]

# ---------------------------------------------------------------------------
# 3. Methodology codebook
# ---------------------------------------------------------------------------

METHODS = [
    ("Congress/Conference Report", [
        r"\bers international congress\b", r"^highlights from\b",
        r"\bconference\b.*\bhighlights\b",
    ]),
    ("Study Protocol / Trial Design", [
        r"\bprotocol\b", r"\btrial design\b", r"\brationale and design\b",
        r"\bstudy design\b", r"\bdesign of the\b", r"\bcohort profile\b",
        r"\bblueprint\b",
    ]),
    ("Systematic Review / Meta-analysis", [
        r"\bsystematic review\b", r"\bmeta-analysis\b", r"\bmeta-regression\b",
        r"\bumbrella review\b", r"\bnetwork meta-analysis\b",
        r"\bscoping review\b", r"\bmeta-ethnography\b", r"\bqualitative synthesis\b",
    ]),
    ("Guideline / Consensus / Delphi", [
        r"\bdelphi\b", r"\bconsensus\b", r"\bexpert panel\b",
        r"\bguideline\w*\b", r"\bstandards for\b", r"\bposition (paper|statement)\b",
    ]),
    ("Randomised Controlled Trial", [
        r"\brandomised\b", r"\brandomized\b", r"\brct\b",
        r"\bplacebo-controlled\b", r"\bdouble-blind\b", r"\bcrossover (study|trial)\b",
        r"\bphase (i|ii|iii|1|2|3|2a)\b", r"\bstepped wedge\b",
    ]),
    ("Pilot / Feasibility Study", [
        r"\bpilot\b", r"\bfeasibility\b", r"\bexploratory study\b",
        r"\bproof of concept\b",
    ]),
    ("Qualitative / Mixed Methods / Survey", [
        r"\bqualitative\b", r"\bfocus group\w*\b", r"\bmixed-methods\b",
        r"\bmixed methods\b", r"\bsurvey\b", r"\binterview\w*\b",
        r"\bpatient experience\b", r"\bpatient preference\w*\b",
        r"\bdiscrete choice experiment\b", r"\bpatient-reported outcome\w*\b",
        r"\bacceptab\w*\b", r"\battitudes\b",
    ]),
    ("Machine Learning / AI", [
        r"\bmachine learning\b", r"\bartificial intelligence\b",
        r"\bdeep learning\b", r"\balgorithm\b", r"\bexplainable\b",
        r"\bcomputational platform\b", r"\bautomated\b",
    ]),
    ("Imaging / Radiology", [
        r"\bcomputed tomography\b", r"\bct\b", r"\bmagnetic resonance imaging\b",
        r"\bmri\b", r"\bultrasound\b", r"\bradiograph\w*\b", r"\bimaging\b",
        r"\bechocardiograph\w*\b", r"\bsonographic\b", r"\bradiological\b",
        r"\bhyperpolarised\b", r"\bscintigraph\w*\b", r"\belectrical impedance tomography\b",
        r"\boptical coherence tomography\b",
    ]),
    ("Diagnostic Accuracy / Prediction / Validation", [
        r"\bvalidation\b", r"\bvalidated\b", r"\bpredictive model\b",
        r"\bprediction model\b", r"\bprediction of\b", r"\brisk score\b",
        r"\bdiagnostic yield\b", r"\bdiagnostic accuracy\b",
        r"\bclinical prediction rule\b", r"\bprognostic\b", r"\bpredictors of\b",
        r"\bcprediction\b", r"\bdetection of\b", r"\bscreening\b",
    ]),
    ("Basic / Laboratory Science", [
        r"\bin vitro\b", r"\bin vivo\b", r"\bmouse\b", r"\bmice\b", r"\bmurine\b",
        r"\bswine\b", r"\bcell culture\b", r"\borganoid\w*\b",
        r"\bgene expression\b", r"\bgenome-wide association\b",
        r"\bproteome\b", r"\bmetabolome\b", r"\bmultiomics\b",
        r"\bepithelial cells\b", r"\bmacrophages\b", r"\bautopsy\b",
        r"\bcryobiops\w*\b", r"\bmendelian randomisation\b",
        r"\bexpression\b", r"\bextracellular trap\w*\b", r"\bcomplement\b",
        r"\bsurfactant\b", r"\bprogenitor\b", r"\bremodelling\b",
        r"\bmesenchymal transition\b", r"\bmicrobiot\w*\b", r"\bmicrobiome\b",
        r"\bserum \w+ level\w*\b", r"\bplasma \w+\b", r"\bmatrix metalloproteinase\b",
        r"\bautophagy\b", r"\binflammation\b", r"\bimmun\w*\b",
    ]),
    ("Registry / Database Study", [
        r"\bregistry\b", r"\bregister\b", r"\bnational database\b",
        r"\bnationwide\b", r"\badministrative data\b", r"\bclaims\b",
        r"\bmedicare\b", r"\belectronic health record\w*\b",
        r"\broutinely collected\b", r"\bbiobank\b", r"\bpopulation-based\b",
        r"\breal-world\b", r"\breal-life\b", r"\bnational mortality statistics\b",
    ]),
    ("Cohort Study", [
        r"\bcohort\b", r"\blongitudinal\b", r"\bprospective\b",
        r"\bretrospective\b", r"\bobservational\b", r"\bfollow-up\b",
        r"\bincidence\b",
    ]),
    ("Case-Control Study", [
        r"\bcase-control\b", r"\bmatched cohort\b", r"\bcase series\b",
    ]),
    ("Cross-sectional / Prevalence", [
        r"\bcross-sectional\b", r"\bprevalence\b", r"\bepidemiolog\w*\b",
        r"\bburden of\b",
    ]),
    ("Narrative Review / Editorial", [
        r"\bnarrative review\b", r"\breview\b", r"\bcurrent knowledge\b",
        r"\bupdate on\b", r"\bfuture directions\b", r"\boverview\b",
        r"\bchallenges\b", r"\bperspective\b", r"\bopportunities\b",
        r"\bunmet (clinical )?need\b", r"\badvances in\b", r"\bmanagement of\b",
    ]),
    # ---- broad fallback tiers (lowest priority) ----
    ("Technical / Measurement / Device", [
        r"\bmeasurement\w*\b", r"\bmeasuring\b", r"\bdevice\b", r"\bsensor\b",
        r"\bmonitoring\b", r"\bassay\b", r"\breproducibility\b", r"\bagreement\b",
        r"\breference (values|equations)\b", r"\bnormal values\b", r"\bcalibration\b",
        r"\bnovel method\b", r"\ba new method\b", r"\bdetector\b",
    ]),
    ("Interventional / Treatment Effect (non-randomised)", [
        r"\befficacy\b", r"\beffectiveness\b", r"\bsafety\b", r"\btreatment (with|of)\b",
        r"\bresponse to\b", r"\btherap\w*\b", r"\bintervention\w*\b",
        r"\bsupplementation\b", r"\btolerability\b",
    ]),
    ("Observational - Association / Risk Factor", [
        r"\bassociation\w*\b", r"\bassociated with\b", r"\brisk factor\w*\b",
        r"\bdeterminants\b", r"\bcorrelat\w*\b", r"\bimpact of\b",
        r"\binfluence of\b", r"\beffects? of\b", r"\brelationship\b",
        r"\brelated to\b", r"\bpredict\w*\b",
    ]),
    ("Descriptive Clinical Study", [
        r"\bclinical characteristics\b", r"\bcharacteristics\b", r"\bcharacterisation\b",
        r"\boutcomes?\b", r"\bexperience\b", r"\bpractice\w*\b", r"\bpatterns\b",
        r"\btrends\b", r"\bdemographics\b", r"\bphenotyp\w*\b", r"\bclusters?\b",
        r"\bprofile\b", r"\bspectrum\b", r"\bfeatures\b", r"\buse of\b",
        r"\bcomparison of\b", r"\bassessment of\b", r"\bevaluation of\b",
        r"\bidentification of\b", r"\brole of\b", r"\bmortality\b",
        r"\bquality of life\b", r"\bsymptoms\b", r"\bcomorbidit\w*\b",
        r"\bamong patients\b", r"\bin patients with\b", r"\bmulticentre\b",
        r"\binternational study\b", r"\bgeneral population\b",
    ]),
]


# ---------------------------------------------------------------------------
# 4. Classifier
# ---------------------------------------------------------------------------

# Titles describing outcomes measured in adulthood should not be coded as
# paediatric merely because the cohort was recruited in childhood.
ADULT_OUTCOME = re.compile(
    r"\badults?\b|\byoung men\b|\byoung women\b|\bmiddle-aged\b"
    r"|\bto adulthood\b|\bin adulthood\b|\byoung adult\w*\b|\belderly\b"
)


def classify(text: str, codebook, doc_type: str = "") -> tuple:
    """Return (primary_label, all_matched_labels, n_rules_fired)."""
    scores = []
    for idx, (label, patterns) in enumerate(codebook):
        hits = sum(1 for p in patterns if re.search(p, text))
        if label == "Paediatrics / Neonatal" and hits and ADULT_OUTCOME.search(text):
            hits -= 1          # demote, do not veto
        if hits:
            scores.append((hits, -idx, label))
    if not scores:
        return ("Other / Unclassified", "", 0)
    scores.sort(reverse=True)
    primary = scores[0][2]
    all_labels = "; ".join(s[2] for s in sorted(scores, reverse=True))
    return (primary, all_labels, scores[0][0])


def load_wos(path: str) -> pd.DataFrame:
    """Load either a Web of Science .xlsx export or an OpenAlex .csv window.

    Both carry the same key columns (UT, Item Title, Publication Year,
    Document Type, Number of Citations), so downstream coding is identical.
    """
    if str(path).lower().endswith(".csv"):
        df = pd.read_csv(path)
        missing = {"UT", "Item Title", "Publication Year", "Document Type",
                   "Number of Citations"} - set(df.columns)
        if missing:
            raise ValueError(f"CSV is missing required columns: {missing}")
        df = df.dropna(subset=["UT", "Item Title"]).reset_index(drop=True)
        df["Number of Citations"] = pd.to_numeric(df["Number of Citations"],
                                                  errors="coerce")
        return df

    raw = pd.read_excel(path, sheet_name=0, header=None)
    # find the header row (the one containing 'Item Title')
    hdr = None
    for i in range(min(15, len(raw))):
        if raw.iloc[i].astype(str).str.contains("Item Title", na=False).any():
            hdr = i
            break
    if hdr is None:
        raise ValueError("Could not locate header row containing 'Item Title'")
    df = raw.iloc[hdr + 1:].copy()
    df.columns = raw.iloc[hdr].tolist()
    df = df.dropna(subset=["UT", "Item Title"]).reset_index(drop=True)
    df["Number of Citations"] = pd.to_numeric(df["Number of Citations"],
                                              errors="coerce")
    return df


def main(inp: str, out: str):
    df = load_wos(inp)
    df["clean_title"] = df["Item Title"].map(normalise)

    theme_res = df["clean_title"].map(lambda t: classify(t, THEMES))
    meth_res = df["clean_title"].map(lambda t: classify(t, METHODS))

    df["Theme"] = [r[0] for r in theme_res]
    df["Theme_all_matches"] = [r[1] for r in theme_res]
    df["Theme_rule_hits"] = [r[2] for r in theme_res]

    df["Methodology"] = [r[0] for r in meth_res]
    df["Methodology_all_matches"] = [r[1] for r in meth_res]
    df["Methodology_rule_hits"] = [r[2] for r in meth_res]

    # Honest fallback rather than a forced label
    art = df["Document Type"].astype(str).str.strip().eq("Article")
    unc = df["Methodology"].eq("Other / Unclassified")
    df.loc[art & unc, "Methodology"] = "Original research - design not stated in title"

    # Document type overrides: WoS 'Review' is authoritative for methodology
    is_review = df["Document Type"].astype(str).str.strip().eq("Review")
    keep = df["Methodology"].isin(
        ["Systematic Review / Meta-analysis", "Congress/Conference Report",
         "Guideline / Consensus / Delphi"])
    df.loc[is_review & ~keep, "Methodology"] = "Narrative Review / Editorial"

    # Confidence flag for manual review
    def conf(hits):
        return "High" if hits >= 2 else ("Medium" if hits == 1 else "Low")

    df["Theme_confidence"] = df["Theme_rule_hits"].map(conf)
    df["Methodology_confidence"] = df["Methodology_rule_hits"].map(conf)
    df["Needs_review"] = (
        df["Theme_confidence"].eq("Low") | df["Methodology_confidence"].eq("Low")
    )

    df["Citation_band"] = pd.cut(
        df["Number of Citations"],
        bins=[-0.1, 0.5, 1.5, 4.5, 9.5, 1e9],
        labels=["0", "1", "2-4", "5-9", "10+"])
    df["Zero_cited"] = df["Number of Citations"].eq(0)
    df["Low_cited_0_1"] = df["Number of Citations"].le(1)

    df.to_csv(out, index=False)
    return df


if __name__ == "__main__":
    import sys
    d = main(sys.argv[1], sys.argv[2])
    print(f"Coded {len(d)} records")
    print("\nTHEME:")
    print(d["Theme"].value_counts().to_string())
    print("\nMETHODOLOGY:")
    print(d["Methodology"].value_counts().to_string())
    print(f"\nLow-confidence (needs review): {d['Needs_review'].sum()}")
