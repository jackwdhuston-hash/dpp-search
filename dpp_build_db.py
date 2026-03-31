"""
DPP Database Builder
--------------------
Builds a SQLite full-text-search database from the extracted text files.
Creates dpp.db with two tables:
  - papers: metadata for each paper
  - chunks: overlapping text chunks, indexed for full-text search
Run with: python3 dpp_build_db.py
"""

import os
import re
import sqlite3
from rich.console import Console
from rich.progress import track

TEXT_DIR   = "dpp_texts"
DB_PATH    = "dpp.db"

CHUNK_SIZE  = 400   # words per chunk
CHUNK_STEP  = 300   # start next chunk every N words (100-word overlap)

console = Console()

# Paper metadata — maps filename stem to (title, author, volume, theme)
METADATA = {
    "01opening-unsustainability":                       ("Editorial: Opening Lines", "Willis", "1.1", "Unsustainability"),
    "02manzinisustainable_wellbeing":                   ("Scenarios of Sustainable Wellbeing", "Manzini", "1.1", "Unsustainability"),
    "03berquedisurbanity":                              ("The Idea of Disurbanity", "Berque", "1.1", "Unsustainability"),
    "04frysustainment":                                 ("The Voice of Sustainment", "Fry", "1.1", "Unsustainability"),
    "05fryhotdebate":                                   ("Watch this Space: Hot Debate", "Fry", "1.1", "Unsustainability"),
    "01tainted_beauty":                                 ("Editorial: Tainted Beauty", "Willis", "1.2", "Beauty"),
    "02harriesmask_and_veil":                           ("Why Beauty Matters", "Harries", "1.2", "Beauty"),
    "03tonkinwisebeauty_in_use":                        ("Beauty-in-Use", "Tonkinwise", "1.2", "Beauty"),
    "04fryphilosophysustainment":                       ("Why Philosophy?", "Fry", "1.2", "Beauty"),
    "05sustainmentheideggermcneill":                    ("Approaching the Sustainment with Heidegger", "McNeill", "1.2", "Beauty"),
    "06dilnotfrymanifestoredirectivedesign":            ("Manifesto for Redirective Design", "Fry & Dilnot", "1.2", "Beauty"),
    "01mediage":                                        ("Editorial: Mediage", "Willis", "1.3", "Mediage"),
    "02frytelevisual_designing":                        ("Televisual Designing", "Fry", "1.3", "Mediage"),
    "03lopestelevisual_anaesthesia":                    ("Televisual Anaesthesia", "Lopes", "1.3", "Mediage"),
    "04paradox_of_user_control":                        ("The Paradox of User Control", "Palmer", "1.3", "Mediage"),
    "05frytouching_the_wall_of_silence":                ("Touching the Wall of Silence", "Fry", "1.3", "Mediage"),
    "01technology_as_environment":                      ("Editorial: Technology as Environment", "Willis", "1.4", "Technology as Environment"),
    "02rapt_in_technology":                             ("Rapt in Technology", "Davison", "1.4", "Technology as Environment"),
    "03computing_against_the_grain":                    ("Computing Against the Grain", "Makelburge", "1.4", "Technology as Environment"),
    "04fryelimination_by_design":                       ("Elimination by Design", "Fry", "1.4", "Technology as Environment"),
    "05manzinisustainable_everyday":                    ("Sustainable Everyday", "Manzini & Jegou", "1.4", "Technology as Environment"),
    "06frythe_impossible":                              ("The Impossible", "Fry", "1.4", "Technology as Environment"),
    "01design_time_education":                          ("Editorial: Design Time and Education", "Willis", "1.5", "Design-Time"),
    "02wooddesigning_clocks":                           ("Designing Clocks to Sustain Synergy", "Wood", "1.5", "Design-Time"),
    "04jonasdesign_timenot_knowing":                    ("Design, Time and Not Knowing", "Jonas", "1.5", "Design-Time"),
    "05friedmandesign_education_in_the_university":     ("Design Education in the University", "Friedman", "1.5", "Design-Time"),
    "09frydead_institution_walking":                    ("Dead Institution Walking", "Fry", "1.5", "Design-Time"),
    "11frydialectic_of_sustainment":                    ("The Dialectic of Sustainment", "Fry", "1.5", "Design-Time"),
    "01design_s_other":                                 ("Editorial: Design's Other", "Willis", "1.6", "Design's Other"),
    "03akkachdesign_eurocentricity":                    ("Design and the Question of Eurocentricity", "Akkach", "1.6", "Design's Other"),
    "06frydesigning_betwixt_design_s_others":           ("Betwixt Design's Others", "Fry", "1.6", "Design's Other"),
    "09frydesign_and_the_political":                    ("Design and the Political", "Fry", "1.6", "Design's Other"),
    "11fryother_economy":                               ("An Other Economy", "Fry", "1.6", "Design's Other"),
    "01usercentreddesignwillis":                        ("Editorial: User-Centred Design", "Willis", "2.1", "User-Centred Design"),
    "06fry_designother_and_the_ethical":                ("Design, The Other and the Ethical", "Fry", "2.1", "User-Centred Design"),
    "05tonkinwiseethos_of_things":                      ("Ethics by Design, or the Ethos of Things", "Tonkinwise", "2.2", "Design Ethics"),
    "06frydesign_ethics_as_futuring":                   ("Design Ethics as Futuring", "Fry", "2.2", "Design Ethics"),
    "02borgmaninformation_and_inhabitation":            ("Information & Inhabitation", "Borgmann", "2.3", "Rematerialization 1"),
    "03tonkinwisedematerialisation_and_changing_things":("Is Design Finished?", "Tonkinwise", "2.3", "Rematerialization 1"),
    "04fryrematerialisation":                           ("Rematerialisation as a Prospective Project", "Fry", "2.3", "Rematerialization 1"),
    "02fryurbocentrism_to_hyperurbanism":               ("From Urbocentrism to Hyperurbanism", "Fry", "2.4", "Urbocentrism"),
    "03street_lights_at_the_end_of_the_universe":       ("Street Lights at the End of the Universe", "Davison", "2.4", "Urbocentrism"),
    "06frydesign_intelligence":                         ("On Design Intelligence", "Fry", "2.4", "Urbocentrism"),
    "01scenarios_futures_and_design":                   ("Scenarios, Futures and Design", "Willis", "3.1", "Scenarios"),
    "03fryscenario_of_design":                          ("The Scenario of Design", "Fry", "3.1", "Scenarios"),
    "02redstromtechnology_as_material_in_design":       ("On Technology as Material in Design", "Redstrom", "3.2", "Rematerialization 2"),
    "03jonasdematerialisation_through_body_orientation":("Dematerialisation through Body Orientation", "Jonas", "3.2", "Rematerialization 2"),
    "04ecologies_of_steel":                             ("Ecologies of Steel", "Fry & Willis", "3.2", "Rematerialization 2"),
    "02design_waste_and_homelessness":                  ("Design, Waste and Homelessness", "Loschiavo dos Santos", "3.3", "Homelessness"),
    "06fryhomelessnessphilosophical_arch":              ("Homelessness: a Philosophical Architecture", "Fry", "3.3", "Homelessness"),
    "03transformation_by_design_or_education":          ("The Material Basis of Everyday Rationality", "Christensen", "3.4", "Design-in-Action"),
    "04more_actingless_making":                         ("More Acting & Less Making", "Bousbaci & Findeli", "3.4", "Design-in-Action"),
    "05design-and-development":                         ("Design, Development & Questions of Direction", "Fry", "3.4", "Design-in-Action"),
    "02review_of_bruce_sterling_shaping_things":        ("Always Historicise Design", "Tonkinwise", "4.1", "Review Issue"),
    "03reviewlatourharmanverbeek":                      ("Object-thing Philosophy and Design", "Fry", "4.1", "Review Issue"),
    "02ontologicaldesigning":                           ("Ontological Designing", "Willis", "4.2", "Design Philosophy Ethics 1"),
    "03designenigmaworldmcneill":                       ("Design and the Enigma of the World", "McNeill", "4.2", "Design Philosophy Ethics 1"),
    "04jonasspecial_moral_code_for_design":             ("A Special Moral Code for Design?", "Jonas", "4.2", "Design Philosophy Ethics 1"),
    "01frydesign_ethics_and_identity":                  ("Design, Ethics & Identity", "Fry", "4.3", "Design Philosophy Ethics 2"),
    "02designtechnologyethcskockelkorentaylor":         ("Design, Technology & Ethics", "Owens", "4.3", "Design Philosophy Ethics 2"),
    "03cyborgsingularity_or_sustainment":               ("A Cyborg's Choice: Singularity or Sustainment?", "Wahl", "4.3", "Design Philosophy Ethics 2"),
    "02blevissustainable_interaction_design":           ("Advancing Sustainable Interaction Design", "Blevis", "4.4", "New Direction"),
    "02fryredirective_practice":                        ("Redirective Practice: An Elaboration", "Fry", "5.1", "Redirection"),
    "05blevisliving_room_totemunsustainable":           ("Living Room Totem of the Unsustainable", "Blevis", "5.1", "Redirection"),
    "02forgotten_projectnew_urbanism":                  ("The Forgotten Project in New Urbanism", "d'Anjou & Weiss", "5.2", "Building Dwelling Futures"),
    "04redirective_practiceboonah":                     ("Redirective Practice in Action", "Fry & Gall", "5.2", "Building Dwelling Futures"),
    "05peri_urbanwillis":                               ("From Peri-urban to Unknown Territory", "Willis", "5.2", "Building Dwelling Futures"),
    "02christensen_sustainableservices_flow":           ("What is so Sustainable about Services?", "Christensen", "5.3", "Everyday Sustainment"),
    "03danjouexistential_self":                         ("The Existential Self as Locus of Sustainability", "d'Anjou", "5.3", "Everyday Sustainment"),
    "02liquid_dropdesign_process":                      ("The Liquid Drop", "Ostlund et al.", "6.1", "Technological Angst"),
    "03stoltermanhci_towardscritical_research":         ("HCI: Towards a Critical Research Position", "Stolterman & Fors", "6.1", "Technological Angst"),
    "05philosophicaldialogue":                          ("Philosophical Dialogue: Everyday Truths?", "McNeill & Christensen", "6.1", "Technological Angst"),
    "06frygap-ability_to_sustain":                      ("The Gap in the Ability to Sustain", "Fry", "6.1", "Technological Angst"),
    "02redirecting_affective_dispositions-philosophy":  ("Redirecting Affective Dispositions", "Christensen", "6.2", "Self, Agency, World"),
    "03enquist_ecology_of_the_distributed_self":        ("A Socio-material Ecology of the Distributed Self", "Enquist", "6.2", "Self, Agency, World"),
    "04poldmadwelling_futures":                         ("Dwelling Futures and Lived Experiences", "Poldma", "6.2", "Self, Agency, World"),
    "01inefficientsustainability":                      ("Inefficient Sustainability", "Willis & Tonkinwise", "7.1", "Inefficient Sustainability"),
    "02stoeklgleaning":                                 ("Gift, Design and Gleaning", "Stoekl", "7.1", "Inefficient Sustainability"),
    "03unnatural_capital_bataille_beyond_design":       ("Unnatural Capital: Bataille beyond Design", "Hunt", "7.1", "Inefficient Sustainability"),
    "04frysustainabilityinsufficiency":                 ("Sustainability: Inefficiency or Insufficiency?", "Fry", "7.1", "Inefficient Sustainability"),
    "05reviewofallan_stoeklbataillepeak":               ("Sustainability is not a Humanism", "Tonkinwise", "7.1", "Inefficient Sustainability"),
    "02hall-true_cost_button_pushing":                  ("True Cost Button-pushing", "Hall", "7.2", "Design History Futures 1"),
    "06unsustainabilitybritish_utility":                ("Unsustainability: Towards a New Design History", "Massey & Micklethwaite", "7.2", "Design History Futures 1"),
    "02barberenvironmentalisation_and_environmentalityarchitecture": ("Environmentalisation: 20thc Architecture Reconceived", "Barber", "7.3", "Design History Futures 2"),
    "05fam-systemchangesewers":                         ("Challenge of Systems Change: Sydney's Sewers", "Fam et al.", "7.3", "Design History Futures 2"),
    "02harriessacredarchitecture":                      ("On the Need for Sacred Architecture", "Harries", "8.1", "Sacred Design"),
    "04frysacred_designiii":                            ("Re-turning: Sacred Design III", "Fry", "8.1", "Sacred Design"),
    "06akkachpresence_of_absence":                      ("The Presence of Absence: Sacred Design Now", "Akkach", "8.1", "Sacred Design"),
    "02shanaagid-social_design-politicalcontexts":      ("How Do We Transition People?", "Agid", "9.3", "Beyond Progressive Design 1"),
    "03kiemdesigningsocial-innovation":                 ("Designing the Social, and Social Innovation", "Kiem", "9.3", "Beyond Progressive Design 1"),
    "02viscommvodeb":                                   ("Beyond the Image and Towards Communication", "Vodeb", "10.1", "Beyond Progressive Design 2"),
    "03design-withoutdesigners":                        ("Design without Designers", "Raff & Melles", "10.1", "Beyond Progressive Design 2"),
    "06zenhumancentredpractitioner":                    ("A Way of Being in Design: Zen", "Akama", "10.1", "Beyond Progressive Design 2"),
    "07dwellingdestruction_and_design":                 ("Home Eco-Nomy: Dwelling, Destruction and Design", "Perolini & Fry", "10.1", "Beyond Progressive Design 2"),
    "02ontologicaldesigmappingwillis":                  ("The Ontological Designing of Mapping", "Willis", "10.2", "Mapping"),
    "02keshavarzdissensus":                             ("Design and Dissensus", "Keshavarz & Maze", "11.1", "Design, Politics, Change"),
    "03kiemreviewdisalvoadversarialdesign":             ("If Political Design Changed Anything", "Kiem", "11.1", "Design, Politics, Change"),
    "06serviceinterfacephilipsdirectlife":              ("Thinking through the Service Interface", "Secomandi", "11.1", "Design, Politics, Change"),
    "1fryorigin-work_of_design":                        ("The Origin of the Work of Design", "Fry", "12.1", "The Work of Design"),
    "2townsendcomplexity_and_control":                  ("Complexity and Control", "Townsend", "12.1", "The Work of Design"),
    "3ghassanearth_with_agency":                        ("Earth with Agency: A Thoroughly Queer Notion", "Ghassan", "12.1", "The Work of Design"),
    "5boano-agambenurbandesign":                        ("Agamben's Gesture of Profanation", "Boano & Talocci", "12.1", "The Work of Design"),
    "1kalantidoufuture_of_athens":                      ("Westernizing the Semi-Orient", "Kalantidou", "12.2", "Cities, Futures"),
    "2boehnertdesign_industry":                         ("Design vs. the Design Industry", "Boehnert", "12.2", "Cities, Futures"),
    "4willisdesignbackfuture":                          ("Designing Back from the Future", "Willis", "12.2", "Cities, Futures"),
    "6tonkinwisedunne-raby":                            ("How We Intend to Future", "Tonkinwise", "12.2", "Cities, Futures"),
    "2escobartransiciones":                             ("Transiciones", "Escobar", "13.1", "Transition Design"),
    "1irwin-et-alprovocation":                          ("Transition Design Provocation", "Irwin, Kossoff & Tonkinwise", "13.1", "Transition Design"),
    "3kossoff-holism":                                  ("Holism and the Reconstitution of Everyday Life", "Kossoff", "13.1", "Transition Design"),
    "4damianwhitemetaphorshrybridity":                  ("Metaphors, Hybridity, Failure and Work", "White", "13.1", "Transition Design"),
    "8willis-refusediscipline":                         ("Transition Design: Refuse Discipline", "Willis", "13.1", "Transition Design"),
    "10tonkinwisefrom_and_to_what":                     ("Design for Transitions - from and to what?", "Tonkinwise", "13.1", "Transition Design"),
    "1keshavarzmaterial_practices1-passporting":        ("Material Practices of Power I", "Keshavarz", "13.2", "Power, Matter, Body"),
    "2dilnot-the_matter_of_design":                     ("The Matter of Design", "Dilnot", "13.2", "Power, Matter, Body"),
    "3ventura-uncannymechanics":                        ("Uncanny Mechanics", "Ventura", "13.2", "Power, Matter, Body"),
    "1keshavarzmaterial_practices-of-power2":           ("Material Practices of Power II", "Keshavarz", "14.1", "Power and Social Design"),
    "4ghassan-designer_as_minor_scientist":             ("Fluidity and Legitimacy: Designer as Minor Scientist", "Ghassan & Blythe", "14.1", "Power and Social Design"),
    "01designglobalsoutheditorial":                     ("Editorial: Design and the Global South", "Fry & Willis", "15.1", "Global South"),
    "02frypositionpaper":                               ("Design for/by The Global South", "Fry", "15.1", "Global South"),
    "03arturoescobar":                                  ("Response: Design for/by the Global South", "Escobar", "15.1", "Global South"),
    "04madinatlostanovadecolonizingdesign":             ("On Decolonizing Design", "Tlostanova", "15.1", "Global South"),
    "05hernan-daniel-alterdesign":                      ("Alter Design", "Lopez-Garay & Lopera Molano", "15.1", "Global South"),
    "08vazquezprecedenceearthanthropocene":             ("Precedence, Earth and the Anthropocene", "Vazquez", "15.1", "Global South"),
    "02designafterdesign":                              ("Design After Design", "Fry", "15.2", "Design After Design"),
    "03materialcntrldigitalfabrication":                ("Material Control: Digital Fabrication", "McMeel", "15.2", "Design After Design"),
    "05design-aestheticexperience_":                    ("Design and Contemporary Aesthetic Experiences", "Folkmann & Jensen", "15.2", "Design After Design"),
    "06designknowledgehumaninterest":                   ("Design, Knowledge and Human Interest", "Dilnot", "15.2", "Design After Design"),
}


def chunk_text(text, chunk_size=CHUNK_SIZE, step=CHUNK_STEP):
    """Split text into overlapping word-chunks."""
    words = text.split()
    chunks = []
    for start in range(0, len(words), step):
        chunk = " ".join(words[start:start + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
        if start + chunk_size >= len(words):
            break
    return chunks


def build():
    # Remove old DB if it exists
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        console.print(f"[yellow]Removed existing {DB_PATH}[/yellow]")

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    # Papers table
    cur.execute("""
        CREATE TABLE papers (
            id      INTEGER PRIMARY KEY,
            stem    TEXT UNIQUE,
            title   TEXT,
            author  TEXT,
            volume  TEXT,
            theme   TEXT
        )
    """)

    # Chunks table with FTS5 virtual table for full-text search
    cur.execute("""
        CREATE TABLE chunks (
            id          INTEGER PRIMARY KEY,
            paper_id    INTEGER REFERENCES papers(id),
            chunk_index INTEGER,
            text        TEXT
        )
    """)

    cur.execute("""
        CREATE VIRTUAL TABLE chunks_fts USING fts5(
            text,
            content='chunks',
            content_rowid='id',
            tokenize='porter unicode61'
        )
    """)

    con.commit()

    txt_files = sorted([f for f in os.listdir(TEXT_DIR) if f.endswith('.txt')])
    total_chunks = 0
    unmatched = []

    console.print(f"\n[bold]Building database from {len(txt_files)} text files...[/bold]\n")

    for filename in track(txt_files, description="Processing..."):
        stem = filename.replace('.txt', '')
        txt_path = os.path.join(TEXT_DIR, filename)

        meta = METADATA.get(stem)
        if not meta:
            unmatched.append(stem)
            title, author, volume, theme = stem, "Unknown", "?", "?"
        else:
            title, author, volume, theme = meta

        # Insert paper record
        cur.execute(
            "INSERT INTO papers (stem, title, author, volume, theme) VALUES (?,?,?,?,?)",
            (stem, title, author, volume, theme)
        )
        paper_id = cur.lastrowid

        # Read text and chunk it
        with open(txt_path, 'r', encoding='utf-8') as f:
            text = f.read()

        chunks = chunk_text(text)
        total_chunks += len(chunks)

        for i, chunk in enumerate(chunks):
            cur.execute(
                "INSERT INTO chunks (paper_id, chunk_index, text) VALUES (?,?,?)",
                (paper_id, i, chunk)
            )

    # Populate FTS index
    cur.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild')")
    con.commit()
    con.close()

    console.print(f"\n[green bold]Done![/green bold]")
    console.print(f"  Papers indexed : {len(txt_files)}")
    console.print(f"  Total chunks   : {total_chunks:,}")
    console.print(f"  Database        : {os.path.abspath(DB_PATH)}")

    if unmatched:
        console.print(f"\n[yellow]No metadata found for {len(unmatched)} files (indexed with unknown metadata):[/yellow]")
        for s in unmatched:
            console.print(f"  {s}")


if __name__ == "__main__":
    build()
