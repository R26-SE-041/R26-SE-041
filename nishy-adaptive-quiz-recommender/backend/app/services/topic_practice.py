"""Reviewed topic-only practice; independent of uploads and remote model uptime."""
import re
from app.services.biology_recovery import reviewed_source_candidates

# The choices address the same mechanism. Answers and explanations are reviewed
# facts, rather than a word-matched option inferred from a question-paper PDF.
LIPIDS = {
    "hard": [
        ("A phospholipid suspension forms bilayers in water, while triglyceride forms droplets. Which structural difference explains both arrangements?",
         "Phospholipids have polar heads and nonpolar tails; triglycerides lack a comparable polar head",
         ["Phospholipids contain only polar groups; triglycerides contain only phosphate groups", "Both contain identical polar heads but differ only in molecular mass", "Triglycerides have two charged heads while phospholipids have none", "Phospholipids are water-soluble proteins whereas triglycerides are carbohydrates"],
         "Phospholipids are amphipathic: their heads interact with water while their tails avoid it. Triglycerides are predominantly nonpolar and aggregate into droplets rather than forming the same bilayer arrangement."),
        ("A cell loses membrane phospholipids but retains its stored triglycerides. Which paired outcome follows despite an unchanged energy reserve?",
         "Compartment boundaries deteriorate while stored chemical fuel remains available",
         ["Compartment boundaries improve while all energy reserves disappear", "DNA replication stops because triglycerides replace nucleotide bases", "Protein primary structure changes while every membrane remains intact", "All triglycerides become membrane channels without further synthesis"],
         "Phospholipids are major structural constituents of cellular membranes. Triglycerides store chemical energy, so retaining them does not replace the membrane-forming function of phospholipids."),
        ("A membrane contains many saturated fatty-acid tails and becomes rigid when cooled. Which change would preserve fluidity without shortening those tails?",
         "Introduce cis double bonds that prevent close packing",
         ["Remove every double bond to straighten all tails", "Increase hydrogen bonding between adjacent hydrocarbon tails", "Replace every polar head with another saturated tail", "Extend all saturated tails while retaining their original packing"],
         "Cis double bonds introduce bends that hinder close packing of fatty-acid tails. This reduces interactions that otherwise favour rigid packing at low temperature."),
        ("Hydrogenation raises a vegetable oil's melting point while leaving its carbon-chain lengths largely unchanged. Which molecular change explains the altered physical state?",
         "Fewer double bonds allow the hydrocarbon chains to pack more closely",
         ["Additional phosphate groups convert all triglycerides into phospholipids", "Longer peptide chains create more protein cross-links", "Extra glycosidic bonds connect all fatty acids to glucose", "Removal of glycerol creates more cis bends in every tail"],
         "Hydrogenation reduces carbon-carbon double bonds. The resulting straighter chains can pack more closely, generally increasing the melting point without needing longer carbon chains."),
        ("After complete hydrolysis yields glycerol and three fatty acids but no phosphate, which lipid structure best accounts for all observed products?",
         "A glycerol backbone esterified to three fatty acids",
         ["A glycerol backbone attached to two fatty acids and a phosphate head", "Four fused carbon rings with one hydroxyl group", "A long-chain alcohol esterified to one fatty acid", "A chain of amino acids linked by peptide bonds"],
         "A triglyceride consists of glycerol esterified to three fatty acids. Hydrolysis breaks those ester bonds, releasing glycerol and fatty acids without a phosphate-containing head group."),
        ("Bile delivery stops although pancreatic lipase remains active. Why does fat digestion decline despite continued enzyme production?",
         "Reduced emulsification leaves less fat surface accessible to lipase",
         ["Bile normally supplies the peptide bonds that lipase must break", "Bile normally hydrolyses all triglycerides without any enzymes", "Without bile, lipase converts fatty acids directly into glucose", "Lipase can act only after all fatty acids become saturated"],
         "Bile salts help disperse large triglyceride droplets into smaller droplets. This increases the surface available to lipase; reduced emulsification can therefore limit digestion even when the enzyme is present."),
        ("Oxygen diffusion is observed through a lipid bilayer while sodium-ion movement is strongly restricted. Which feature explains this difference beyond molecule size alone?",
         "The hydrophobic interior favours nonpolar solutes over hydrated charged ions",
         ["The bilayer contains permanent open pores for all gases and ions", "Its fatty-acid tails are strongly positively charged", "Sodium ions dissolve freely in hydrocarbon chains but oxygen cannot", "Polar heads actively pump oxygen using ATP"],
         "Oxygen is small and nonpolar, so it can diffuse through the bilayer's hydrophobic core. Charged, hydrated ions face a substantial barrier and commonly require membrane transport proteins."),
        ("A steroid hormone crosses a cell membrane and binds an intracellular receptor, while a charged messenger cannot enter freely. Which property explains the difference?",
         "The steroid's lipid-soluble structure allows passage through the hydrophobic membrane core",
         ["The steroid must first be digested into amino acids at the cell surface", "Its receptor dissolves the entire plasma membrane before binding", "Every charged messenger is larger than every steroid molecule", "All steroids enter only through sodium-selective channels"],
         "Steroid hormones are derived from cholesterol and are sufficiently lipid soluble to cross membranes. A charged messenger generally cannot traverse the hydrophobic core freely."),
        ("Phospholipase removes a fatty-acid tail from many membrane phospholipids while cholesterol remains intact. Which change directly threatens normal bilayer organisation?",
         "Altered head-to-tail balance changes the packing of membrane lipids",
         ["Loss of DNA bases eliminates all complementary pairing", "Formation of peptide bonds turns the membrane into a protein chain", "Cholesterol gains three fatty-acid tails and becomes stored starch", "Every phospholipid becomes a fully saturated triglyceride"],
         "Bilayer organisation depends on the geometry and amphipathic properties of its lipids. Removing a fatty-acid tail changes molecular shape and packing even when cholesterol is still present."),
        ("Fat oxidation releases substantial energy, yet an animal deprived of oxygen cannot sustain aerobic ATP production from fatty acids. Which explanation links both observations?",
         "Reduced fatty-acid carbons yield electrons whose aerobic oxidation depends on oxygen",
         ["Fatty acids store no chemical energy until oxygen is incorporated into glycerol", "All lipid digestion requires oxygen as the active-site component of lipase", "Oxygen converts every fatty acid directly into a ribosome", "Fat oxidation produces ATP only by joining fatty acids to phosphate heads"],
         "Fatty acids contain highly reduced carbon that can supply electrons during oxidation. Sustained aerobic ATP production depends on electron transfer ultimately to oxygen through the respiratory chain."),
        ("A cell synthesises fatty-acid tails normally but cannot produce phospholipid head groups. Which function fails despite continued synthesis of neutral fats?",
         "Assembly of normal amphipathic membrane lipids",
         ["Storage of all genetic information in triglycerides", "Formation of peptide bonds in every enzyme", "Conversion of all saturated fatty acids into cellulose", "Direct incorporation of neutral fat into chromosome bases"],
         "Phospholipids require a hydrophilic head as well as hydrophobic tails to form normal membrane structures. Neutral-fat production alone cannot supply this amphipathic organisation."),
        ("A wax coating reduces water loss from a leaf while its internal membranes remain selectively permeable. Which distinction explains these different lipid functions?",
         "Surface wax forms a hydrophobic barrier; membrane lipids form an organised bilayer",
         ["Wax contains channels that actively pump water while membranes have no hydrophobic regions", "Wax is a glucose polymer while every membrane lipid is a protein", "Internal membrane lipids form a completely impermeable solid shell", "Both functions require wax molecules to act as ribosomal enzymes"],
         "Waxes provide a water-repellent surface barrier. Membrane phospholipids instead assemble into bilayers whose structure, together with proteins, supports selective exchange."),
        ("A triglyceride loses one fatty-acid chain by hydrolysis while a phospholipid retains its phosphate head. Why are their remaining structures still chemically distinguishable?",
         "The phosphate-containing head remains a defining feature of the phospholipid",
         ["Every hydrolysed triglyceride automatically acquires a phosphate head", "Both molecules become identical single glucose units", "Only triglycerides can contain carbon or hydrogen", "A phospholipid necessarily loses its glycerol backbone whenever a triglyceride is hydrolysed"],
         "Breaking an ester bond in a triglyceride does not add a phosphate group. A phospholipid's phosphate-containing head therefore distinguishes it from the partial hydrolysis products of neutral fat."),
        ("After equal masses of fat and carbohydrate are oxidised completely, more energy is released from fat. Which molecular feature explains this difference?",
         "Fatty-acid carbons are more highly reduced and yield more energy on complete oxidation",
         ["Fat contains more peptide bonds than protein and is copied by ribosomes", "Carbohydrate cannot be oxidised in any animal cell", "Fat has no carbon atoms and releases energy solely from phosphate", "Both supply identical energy per mass because all carbon compounds are equally reduced"],
         "Fatty-acid hydrocarbon chains are highly reduced. Their complete oxidation releases more energy per unit mass than the oxidation of carbohydrate, whose carbons are already more oxidised."),
        ("After a cell replaces unsaturated membrane tails with equally long saturated tails, permeability and fluidity change. Which molecular interaction provides the best explanation?",
         "Straighter saturated tails pack closely and strengthen interactions between adjacent chains",
         ["Saturated tails create more cis bends and prevent all molecular contact", "Every saturated tail becomes a charged phosphate head", "Double bonds increase chain length without changing molecular shape", "Fatty-acid tails form complementary base pairs with cholesterol"],
         "Saturated tails lack the cis-double-bond bends common in unsaturated tails. Closer packing increases interactions between neighbouring chains, tending to reduce membrane fluidity."),
    ],
    "medium": [
        ("If a triglyceride is completely hydrolysed, which products should be detected together?", "Glycerol and fatty acids", ["Amino acids and phosphate", "Glucose and fructose", "Nucleotides and ribose", "Cholesterol and cellulose"], "Triglyceride hydrolysis breaks ester bonds between glycerol and its fatty-acid chains."),
        ("If a membrane must remain fluid at lower temperature, which fatty-acid feature is most helpful?", "Cis double bonds in its hydrocarbon tails", ["An absence of all carbon-carbon double bonds", "Longer fully saturated tails only", "Replacement of all heads with hydrocarbon tails", "Covalent attachment of every lipid to its neighbours"], "Cis double bonds introduce bends and reduce close packing, helping preserve fluidity at lower temperature."),
        ("If bile salts divide fat into smaller droplets, which change helps lipase act?", "A larger total surface area of fat is exposed", ["Triglycerides become enzymes before digestion", "All fatty acids become water-soluble ions immediately", "Every ester bond is converted into a peptide bond", "The amount of substrate falls to zero"], "Smaller droplets expose a larger total surface area, improving the access of lipase to its substrate."),
        ("If phospholipids are placed in water, which arrangement keeps their tails away from water?", "Heads face water while tails face inward", ["Tails face water while all heads face inward", "Heads and tails form a chain of glucose units", "Every tail acquires a positive electrical charge", "Every head becomes a fatty-acid chain"], "Hydrophilic heads interact with water while hydrophobic tails associate away from it."),
        ("If oxygen crosses a lipid bilayer without a transport protein, which property permits this?", "Its small, nonpolar character", ["Its permanent positive charge", "Its peptide backbone", "Its large hydrated ionic shell", "Its ability to hydrolyse every phospholipid"], "Small nonpolar oxygen molecules can dissolve in and diffuse through the bilayer's hydrophobic region."),
        ("If an animal needs a compact long-term energy reserve, which lipid is most suitable?", "Triglyceride", ["Phospholipid head groups alone", "Amino acids joined as collagen", "DNA nucleotides", "Cellulose microfibrils"], "Triglycerides are energy-rich neutral fats commonly stored for long-term fuel use."),
        ("If a lipid contains four fused carbon rings, which class best fits its structure?", "Steroid", ["Triglyceride", "Phospholipid", "Disaccharide", "Polypeptide"], "The steroid framework consists of four fused carbon rings; cholesterol is a familiar example."),
        ("If a leaf develops a thicker wax coating, which water-related effect is expected?", "Less water loss across the coated surface", ["More direct evaporation through the wax", "Conversion of all water into fatty acids", "Loss of every membrane in the leaf", "Movement of all stomata into the roots"], "A hydrophobic wax coating provides a barrier that reduces water loss from the leaf surface."),
        ("If hydrogenation removes double bonds from an oil, which physical change is generally expected?", "Its melting point rises as chains pack more closely", ["Its fatty acids become amino acids", "Its glycerol becomes DNA", "All carbon chains become shorter by half", "Its ester bonds become glycosidic bonds"], "Reducing double bonds makes chains straighter, allowing closer packing and generally raising melting point."),
        ("If a membrane loses many phospholipids while retaining triglyceride stores, which role is directly compromised?", "Formation of selective cellular boundaries", ["Storage of genetic information in chromosomes", "Formation of glucose chains in starch", "Binding of codons to ribosomes", "Production of a cellulose cell wall from triglycerides"], "Phospholipids provide the bilayer structure of membranes; stored triglycerides do not replace that role."),
    ],
    "easy": [
        ("Which alcohol forms the backbone of a triglyceride?", "Glycerol", ["Ethanol", "Methanol", "Ribose", "Glucose"], "Glycerol has three hydroxyl groups that can form ester bonds with fatty acids."),
        ("How many fatty-acid chains are attached to glycerol in a triglyceride?", "Three", ["One", "Two", "Four", "Five"], "A triglyceride has one glycerol molecule esterified to three fatty acids."),
        ("Which bond links fatty acids to glycerol in a triglyceride?", "Ester bond", ["Peptide bond", "Glycosidic bond", "Phosphodiester bond", "Disulfide bond"], "Ester bonds form between glycerol hydroxyl groups and fatty-acid carboxyl groups."),
        ("Which lipid class is a major component of cell-membrane bilayers?", "Phospholipids", ["Triglycerides only", "Waxes only", "Starch", "Collagen"], "Phospholipids have hydrophilic heads and hydrophobic tails, enabling bilayer formation."),
        ("Which type of fatty acid contains no carbon-carbon double bonds?", "Saturated fatty acid", ["Monounsaturated fatty acid", "Polyunsaturated fatty acid", "Amino acid", "Nucleic acid"], "Saturated fatty acids have no carbon-carbon double bonds within their hydrocarbon chains."),
        ("Which molecule is a steroid lipid?", "Cholesterol", ["Glycogen", "Cellulose", "Haemoglobin", "DNA"], "Cholesterol has the four-fused-ring framework characteristic of steroid lipids."),
        ("Which enzyme digests triglycerides?", "Lipase", ["Amylase", "Pepsin", "Trypsin", "Helicase"], "Lipase catalyses the hydrolysis of ester bonds in fats."),
        ("Which feature of a phospholipid interacts most readily with water?", "Its polar head", ["Its hydrocarbon tails", "Its absent peptide chain", "Its carbon-carbon bonds alone", "Its triglyceride droplet"], "The polar head is hydrophilic, whereas the fatty-acid tails are hydrophobic."),
        ("What is the main storage function of triglycerides in animals?", "Long-term energy storage", ["Storage of hereditary information", "Formation of ribosomal RNA", "Catalysis of every cellular reaction", "Production of cellulose walls"], "Triglycerides store energy-rich fatty acids in neutral-fat deposits."),
        ("Which surface lipid helps limit water loss from leaves?", "Wax", ["Glycogen", "Starch", "Haemoglobin", "Keratin"], "A waxy cuticle provides a water-repellent protective surface."),
    ],
}


def reviewed_topic_bank(topic: str) -> list[dict]:
    """Resolve common topic names without treating any typed label as evidence."""
    normalized = re.sub(r"[^a-z0-9]+", " ", topic.casefold()).strip()
    lipid_topic = normalized in {"lipid", "lipids", "fat", "fats", "fats and oils", "lipids and fats"}
    if lipid_topic:
        return [
            {"question": stem, "options": {str(i): text for i, text in enumerate([answer, *wrong], 1)},
             "correct_answer": "1", "model_answer": explanation, "_difficulty": level}
            for level, items in LIPIDS.items()
            for stem, answer, wrong, explanation in items
        ]
    # Reuse reviewed syllabus applications for specifically named concepts.
    candidates = []
    for level in ("hard", "medium", "easy"):
        for candidate, _ in reviewed_source_candidates([{"text": topic, "chunk_id": "topic"}], level):
            candidates.append({**candidate, "_difficulty": level})
    return candidates
