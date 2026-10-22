// Plain-language descriptions of the ten rules, shown in the app's rules guide.
// The technical description (inputs, test cases) is in docs/plan.md in the repository.

export interface RuleInfo {
  id: string
  name: string
  checks: string
  why: string
}

export const RULES: RuleInfo[] = [
  {
    id: 'R1',
    name: 'Identity',
    checks:
      'Which substance this is. It is looked up in the EPA DSSTox registry (through ToxIndex) and confirmed independently in PubChem by InChIKey. An ambiguous name stops the analysis and asks you to choose.',
    why: 'Every later step depends on having the right molecule. A substance missing from a registry is reported as a finding, not treated as an error.',
  },
  {
    id: 'R2',
    name: 'Predicted ≠ observed',
    checks:
      'Every finding is sorted by the label its source gives it (predicted, experimental or curated), not by which tool returned it. A verdict based only on predictions is never shown as a hazard conclusion.',
    why: 'A model output is not a measurement, even when it arrives through an evidence tool.',
  },
  {
    id: 'R3',
    name: 'Disagreement',
    checks: 'Whether the predictions disagree with each other, or with measured Ames results.',
    why: 'Disagreement is information. Averaging it away would hide exactly what a researcher needs to see.',
  },
  {
    id: 'R4',
    name: 'Applicability domain',
    checks: 'Whether a model declined to predict because the substance lies outside the chemistry it was built for.',
    why: 'A model that says "not reliable here" is telling you something about the substance, not just failing.',
  },
  {
    id: 'R5',
    name: 'Independence',
    checks: "Whether the substance, or a piece of evidence, was part of a model's training data.",
    why: 'Agreement with data the model has already seen is expected, so it does not show that the model is right.',
  },
  {
    id: 'R6',
    name: 'Structural support',
    checks:
      'The five most similar compounds with measured Ames results (MutagenLou2023), with their similarity and results. Below a similarity of 0.4, support counts as low. Identity is always checked by InChIKey, never by similarity alone.',
    why: 'A prediction for a substance far from any measured compound rests on very little.',
  },
  {
    id: 'R7',
    name: 'Not retrieved ≠ absent',
    checks: 'Every source that was queried but returned nothing, listed as "not retrieved".',
    why: '"Not found by this analysis" is different from "not mutagenic", and from "never tested".',
  },
  {
    id: 'R8',
    name: 'Nitrosamine context',
    checks:
      "Whether the substance is an N-nitroso compound and, if so, its CPCA category and acceptable intake on the EMA's list.",
    why: 'Nitrosamines are a "cohort of concern" for mutagenic impurities, and the standard Ames test can under-detect them.',
  },
  {
    id: 'R9',
    name: 'Toxicokinetics',
    checks:
      "What the US EPA's httk data says about how the body handles the substance, such as measured half-lives per species.",
    why: 'It shows how far animal results transfer to humans. It is context only and never changes the verdict.',
  },
  {
    id: 'R10',
    name: 'Grounded interpretation',
    checks:
      'The AI-written interpretation may only use numbers and references that appear in the analysis. If it uses anything else, a standard text is shown instead.',
    why: 'The language model may explain the verdict, but never decide it.',
  },
]
