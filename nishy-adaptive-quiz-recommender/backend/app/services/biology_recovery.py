"""Reviewed syllabus practice for question papers when remote generation is unavailable.

These applications are keyed to concepts explicitly present in the selected
material. They are labelled topic_model, never claimed to be entailed by an
unkeyed question paper or passed off as newly generated model output.
"""
import re

# Each tuple is (stem, correct choice, four distractors, explanation).
BANK = [
    ("Lymphatic circulation", ("lymphatic", "lymph"), {
        "hard": [
            ("After lymphatic drainage from one leg is blocked, tissue swelling increases although arterial supply remains normal. Which paired change best explains the swelling?",
             "Interstitial fluid accumulates and protein return to blood decreases",
             ["Capillary filtration stops and tissue proteins disappear", "Venous pressure falls and tissue fluid absorption increases", "Arterial delivery stops and interstitial proteins enter blood faster", "Lymph flow increases and capillary fluid loss decreases"],
             "Lymphatics normally return excess interstitial fluid and escaped plasma proteins to circulation. Obstruction retains both in tissues; the retained proteins also favour further water accumulation."),
            ("An infection enlarges a lymph node, yet lymph continues moving through nearby vessels without a central pump. Which combination explains filtration and directed flow?",
             "Immune cells in nodes and valves assisted by skeletal-muscle contractions",
             ["Red blood cells in nodes and valves generating their own contractions", "Platelets in nodes and high arterial pressure inside all lymphatics", "Antibodies in valves and a separate lymphatic heart", "Capillary pores filtering pathogens and bidirectional vessel flow"],
             "Lymph nodes contain immune cells that help detect material carried by lymph. Lymphatic valves prevent backflow while muscle contractions and pressure changes help propel lymph."),
        ],
        "medium": [("If skeletal muscles remain inactive for a long period, which change in lymphatic return is most likely?", "Return slows because external compression of lymphatic vessels decreases", ["Return accelerates because lymphatic valves contract faster", "Return stops because lymph nodes no longer filter", "Lymph becomes arterial blood inside its vessels", "Lymphatic vessels lose all valves immediately"], "Muscle contractions compress lymphatic vessels and aid flow. Less movement reduces this assistance, while valves continue to resist backflow.")],
        "easy": [("Which vessels return excess tissue fluid to the blood?", "Lymphatic vessels", ["Coronary arteries", "Pulmonary arteries", "Bile ducts", "Ureters"], "Lymphatic vessels collect excess interstitial fluid and return it to the blood through the lymphatic circulation.")],
    }),
    ("Stomatal regulation", ("guard cells", "stomata", "abscisic acid"), {
        "hard": [("After drought raises abscisic acid, guard cells lose potassium while the epidermis remains intact. Which linked changes explain reduced water loss?", "Water leaves guard cells, turgor falls, and stomata close", ["Water enters guard cells, turgor rises, and stomata close", "Water leaves guard cells, turgor rises, and stomata open", "Water enters guard cells, turgor falls, and stomata open", "Potassium loss directly seals the leaf cuticle without changing turgor"], "Ion loss makes guard-cell water potential less negative, favouring water movement out. Falling guard-cell turgor closes the pore and reduces transpiration.")],
        "medium": [("If potassium accumulates in guard cells under favourable conditions, which immediate water movement favours stomatal opening?", "Water enters guard cells by osmosis and raises their turgor", ["Water leaves guard cells and raises their turgor", "Water enters guard cells and destroys their walls", "Water leaves guard cells and lowers epidermal turgor only", "No water moves because ions cannot affect water potential"], "Potassium uptake lowers guard-cell water potential. Osmotic water entry increases turgor and promotes opening of the stomatal pore.")],
        "easy": [("Which cells control the opening and closing of a stomatal pore?", "Guard cells", ["Root-hair cells", "Sieve-tube elements", "Companion cells", "Cork cells"], "Guard cells flank the stomatal pore and regulate its opening through changes in their turgor.")],
    }),
    ("DNA replication", ("dna replication", "helicase", "dna polymerase"), {
        "hard": [("After DNA ligase is inhibited, helicase and polymerase continue functioning. Which observation best distinguishes the primary defect from failure of DNA synthesis?", "New DNA fragments form but remain unjoined on the lagging strand", ["Neither parental strand separates at the replication fork", "No nucleotides can be added to either new strand", "RNA primers become permanent substitutes for both daughter strands", "Only the parental DNA is joined while new DNA unwinds"], "Helicase can still unwind DNA and polymerase can extend new strands. Ligase normally seals remaining breaks between fragments, so lagging-strand fragments remain unjoined."),
                 ("A polymerase mutant cannot extend from an RNA primer, although helicase opens DNA normally. Which paired outcome follows at an active replication fork?", "Strands separate but daughter-DNA elongation is impaired", ["Strands stay paired but DNA elongation accelerates", "Only proteins are copied while DNA elongation remains normal", "RNA primers seal fragments without new DNA synthesis", "Both daughter strands lengthen without needing a template"], "Opening the double helix and extending a new DNA strand are separate operations. Functional helicase can expose the templates, but failed polymerase extension prevents normal daughter-strand elongation.")],
        "medium": [("If helicase stops working during DNA replication, which event is affected before new strands can be extended?", "Separation of the parental DNA strands", ["Joining of completed Okazaki fragments only", "Translation of DNA into polypeptides", "Movement of chromosomes to opposite poles", "Formation of a cellulose cell wall"], "Helicase separates the parental strands to expose templates. Failure to expose them prevents normal continuation of replication.")],
        "easy": [("Which enzyme joins adjacent DNA fragments during replication?", "DNA ligase", ["Helicase", "Amylase", "Pepsin", "RNA polymerase"], "DNA ligase seals breaks in the sugar-phosphate backbone, joining adjacent DNA fragments.")],
    }),
    ("Double fertilisation", ("double fertilization", "double fertilisation", "endosperm", "polar nuclei"), {
        "hard": [("One sperm fertilises the egg, but the second fails to fuse with the polar nuclei. Which paired outcome is expected in the ovule?", "A diploid zygote forms but normal triploid endosperm does not", ["A triploid zygote forms with normal diploid endosperm", "Both a diploid zygote and triploid endosperm form normally", "No zygote forms but a triploid embryo develops", "Two haploid embryos replace both the zygote and endosperm"], "Fusion with the egg forms the diploid zygote independently of the second fusion. Fusion of another sperm with the polar nuclei normally initiates triploid endosperm development.")],
        "medium": [("If a sperm nucleus fuses with two haploid polar nuclei in an angiosperm, what ploidy normally results?", "Triploid", ["Haploid", "Diploid", "Tetraploid", "Pentaploid"], "The sperm contributes one chromosome set and the two polar nuclei contribute two more, producing three sets in the primary endosperm nucleus.")],
        "easy": [("What normally develops from the fertilised egg in an angiosperm?", "The embryo", ["The seed coat", "The fruit wall", "The pollen wall", "The integument"], "The fertilised egg forms a zygote, which develops into the embryo of the seed.")],
    }),
    ("Meiosis and inheritance", ("meiosis", "heterozygous", "genotype", "recombination"), {
        "hard": [("After homologues pair normally, crossing-over is prevented while independent assortment continues. Which outcome distinguishes the affected source of variation?", "Fewer new allele combinations form within each chromosome", ["No maternal or paternal chromosome can enter a gamete", "Every gamete retains the full diploid chromosome number", "All chromosome assortment ceases despite normal segregation", "All inherited alleles change into new mutations"], "Crossing-over exchanges segments between homologous chromosomes and creates new combinations along a chromosome. Independent assortment can still vary which whole maternal and paternal homologues enter a gamete.")],
        "medium": [("If a heterozygous parent Aa is test-crossed with aa, what fraction of offspring is expected to show the recessive phenotype?", "One half", ["One quarter", "Three quarters", "All offspring", "No offspring"], "The heterozygote produces A and a gametes in equal proportions, while the tester contributes only a. Half the offspring are therefore aa under simple Mendelian segregation.")],
        "easy": [("What term describes an individual with two different alleles at a gene locus?", "Heterozygous", ["Homozygous", "Haploid", "Polyploid", "Hemizygous"], "A heterozygous individual carries two different alleles at the specified locus.")],
    }),
    ("Carbon dioxide transport", ("blood ph", "carbon dioxide", "co2 in tissue", "during exercise"), {
        "hard": [("During exercise, tissue carbon dioxide rises while ventilation increases. Which linked process explains the initial blood-pH change and its respiratory compensation?", "Carbonic acid formation increases hydrogen ions; faster ventilation removes carbon dioxide", ["Carbon dioxide consumes hydrogen ions; ventilation retains carbon dioxide", "Oxygen converts directly into acid; ventilation prevents oxygen entry", "Bicarbonate stops forming; ventilation raises blood carbon dioxide further", "Haemoglobin removes all acid; ventilation acts only on nitrogen"], "Carbon dioxide hydration and carbonic-acid dissociation can increase hydrogen-ion concentration. Increasing ventilation helps remove carbon dioxide, reducing this acidifying influence.")],
        "medium": [("If carbon dioxide accumulates in blood while other conditions remain unchanged, which pH change is most likely?", "pH decreases as hydrogen-ion concentration rises", ["pH increases as hydrogen-ion concentration rises", "pH remains fixed because carbon dioxide is insoluble", "pH increases because all bicarbonate disappears", "pH becomes neutral regardless of buffering"], "Dissolved carbon dioxide participates in the carbonic-acid equilibrium. Its accumulation tends to increase hydrogen-ion concentration and lower pH.")],
        "easy": [("Which blood cells transport most oxygen in vertebrates?", "Red blood cells", ["Platelets", "Lymphocytes", "Monocytes", "Neutrophils"], "Red blood cells contain haemoglobin, which carries most oxygen transported by vertebrate blood.")],
    }),
    ("Enzyme action", ("enzyme synthesis", "enzyme activity", "enzymes", "enzyme"), {
        "hard": [("Increasing substrate concentration restores an inhibited enzyme's maximum rate, but more substrate is required at half-maximum rate. Which mechanism explains both observations?", "An inhibitor competes with substrate for the active site", ["The enzyme has been irreversibly denatured", "The inhibitor permanently destroys every substrate molecule", "The inhibitor removes the enzyme's catalytic site entirely", "The reaction has become independent of enzyme concentration"], "Competitive inhibition can be overcome at sufficiently high substrate concentration, leaving maximum rate unchanged. Competition raises the apparent substrate concentration needed for half-maximum rate.")],
        "medium": [("If high temperature changes an enzyme's active-site shape permanently, why does adding more substrate fail to restore its activity?", "Substrate can no longer bind in the required catalytic arrangement", ["Substrate concentration always determines enzyme shape", "The substrate changes the enzyme's amino-acid sequence back", "All enzymes require their active sites to be destroyed first", "Substrate replaces the entire protein without catalysis"], "Denaturation disrupts the shape needed for binding and catalysis. Increasing substrate cannot restore a permanently altered active site.")],
        "easy": [("What is the region of an enzyme where its substrate binds called?", "The active site", ["The anticodon", "The centromere", "The nucleosome", "The stomatal pore"], "The active site binds the substrate and provides the arrangement needed for enzyme catalysis.")],
    }),
]


def reviewed_source_candidates(chunks: list[dict], level: str) -> list[tuple[dict, dict]]:
    """Return reviewed applications only for named concepts in these source chunks."""
    results = []
    for topic, keywords, levels in BANK:
        anchor = next((chunk for chunk in chunks if any(
            re.search(r"\b" + re.escape(word) + r"\b", str(chunk.get("text", "")), re.I)
            for word in keywords
        )), None)
        if anchor is None:
            continue
        for stem, correct, distractors, explanation in levels.get(level, []):
            candidate = {
                "question": stem, "options": {str(i): text for i, text in enumerate([correct, *distractors], 1)},
                "correct_answer": "1", "model_answer": explanation,
                "_topic": topic, "_reviewed_recovery": True,
                "_source_anchor_id": str(anchor.get("chunk_id", "")),
            }
            results.append((candidate, anchor))
    return results
