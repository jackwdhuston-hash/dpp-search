"""
DPP PDF Downloader
------------------
Downloads all Design Philosophy Papers (2003-2017) to a local folder.
Run with: python3 dpp_download.py
"""

import urllib.request
import os
import time

# --- Config ---
OUTPUT_DIR = "dpp_papers"   # folder to save PDFs into
DELAY = 1.0                 # seconds between requests (be polite to the server)

BASE_URL = "https://www.thestudioattheedgeoftheworld.com/uploads/4/7/4/0/47403357/"

# Mimick a real browser so the server doesn't block us
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.thestudioattheedgeoftheworld.com/archive1.html",
    "Accept": "application/pdf,*/*",
}

# All papers: (filename, title, author, volume)
PAPERS = [
    ("01opening-unsustainability.pdf", "Editorial: Opening Lines", "Willis", "Vol 1.1"),
    ("02manzinisustainable_wellbeing.pdf", "Scenarios of Sustainable Wellbeing", "Manzini", "Vol 1.1"),
    ("03berquedisurbanity.pdf", "The Idea of Disurbanity", "Berque", "Vol 1.1"),
    ("04frysustainment.pdf", "The Voice of Sustainment", "Fry", "Vol 1.1"),
    ("05fryhotdebate.pdf", "Watch this Space: Hot Debate", "Fry", "Vol 1.1"),
    ("01tainted_beauty.pdf", "Editorial: Tainted Beauty", "Willis", "Vol 1.2"),
    ("02harriesmask_and_veil.pdf", "Why Beauty Matters", "Harries", "Vol 1.2"),
    ("03tonkinwisebeauty_in_use.pdf", "Beauty-in-Use", "Tonkinwise", "Vol 1.2"),
    ("04fryphilosophysustainment.pdf", "Why Philosophy?", "Fry", "Vol 1.2"),
    ("05sustainmentheideggermcneill.pdf", "Approaching the Sustainment with Heidegger", "McNeill", "Vol 1.2"),
    ("06dilnotfrymanifestoredirectivedesign.pdf", "Manifesto for Redirective Design", "Fry & Dilnot", "Vol 1.2"),
    ("01mediage.pdf", "Editorial: Mediage", "Willis", "Vol 1.3"),
    ("02frytelevisual_designing.pdf", "Televisual Designing", "Fry", "Vol 1.3"),
    ("03lopestelevisual_anaesthesia.pdf", "Televisual Anaesthesia", "Lopes", "Vol 1.3"),
    ("04paradox_of_user_control.pdf", "The Paradox of User Control", "Palmer", "Vol 1.3"),
    ("05frytouching_the_wall_of_silence.pdf", "Touching the Wall of Silence", "Fry", "Vol 1.3"),
    ("01technology_as_environment.pdf", "Editorial: Technology as Environment", "Willis", "Vol 1.4"),
    ("02rapt_in_technology.pdf", "Rapt in Technology", "Davison", "Vol 1.4"),
    ("03computing_against_the_grain.pdf", "Computing Against the Grain", "Makelburge", "Vol 1.4"),
    ("04fryelimination_by_design.pdf", "Elimination by Design", "Fry", "Vol 1.4"),
    ("05manzinisustainable_everyday.pdf", "Sustainable Everyday", "Manzini & Jegou", "Vol 1.4"),
    ("06frythe_impossible.pdf", "The Impossible", "Fry", "Vol 1.4"),
    ("01design_time_education.pdf", "Editorial: Design Time and Education", "Willis", "Vol 1.5"),
    ("02wooddesigning_clocks.pdf", "Designing Clocks to Sustain Synergy", "Wood", "Vol 1.5"),
    ("04jonasdesign_timenot_knowing.pdf", "Design, Time and Not Knowing", "Jonas", "Vol 1.5"),
    ("05friedmandesign_education_in_the_university.pdf", "Design Education in the University", "Friedman", "Vol 1.5"),
    ("09frydead_institution_walking.pdf", "Dead Institution Walking", "Fry", "Vol 1.5"),
    ("11frydialectic_of_sustainment.pdf", "The Dialectic of Sustainment", "Fry", "Vol 1.5"),
    ("01design_s_other.pdf", "Editorial: Design's Other", "Willis", "Vol 1.6"),
    ("03akkachdesign_eurocentricity.pdf", "Design and the Question of Eurocentricity", "Akkach", "Vol 1.6"),
    ("06frydesigning_betwixt_design_s_others.pdf", "Betwixt Design's Others", "Fry", "Vol 1.6"),
    ("09frydesign_and_the_political.pdf", "Design and the Political", "Fry", "Vol 1.6"),
    ("11fryother_economy.pdf", "An Other Economy", "Fry", "Vol 1.6"),
    ("01usercentreddesignwillis.pdf", "Editorial: User-Centred Design", "Willis", "Vol 2.1"),
    ("06fry_designother_and_the_ethical.pdf", "Design, The Other and the Ethical", "Fry", "Vol 2.1"),
    ("05tonkinwiseethos_of_things.pdf", "Ethics by Design, or the Ethos of Things", "Tonkinwise", "Vol 2.2"),
    ("06frydesign_ethics_as_futuring.pdf", "Design Ethics as Futuring", "Fry", "Vol 2.2"),
    ("02borgmaninformation_and_inhabitation.pdf", "Information & Inhabitation", "Borgmann", "Vol 2.3"),
    ("03tonkinwisedematerialisation_and_changing_things.pdf", "Is Design Finished?", "Tonkinwise", "Vol 2.3"),
    ("04fryrematerialisation.pdf", "Rematerialisation as a Prospective Project", "Fry", "Vol 2.3"),
    ("02fryurbocentrism_to_hyperurbanism.pdf", "From Urbocentrism to Hyperurbanism", "Fry", "Vol 2.4"),
    ("03street_lights_at_the_end_of_the_universe.pdf", "Street Lights at the End of the Universe", "Davison", "Vol 2.4"),
    ("06frydesign_intelligence.pdf", "On Design Intelligence", "Fry", "Vol 2.4"),
    ("01scenarios_futures_and_design.pdf", "Scenarios, Futures and Design", "Willis", "Vol 3.1"),
    ("03fryscenario_of_design.pdf", "The Scenario of Design", "Fry", "Vol 3.1"),
    ("02redstromtechnology_as_material_in_design.pdf", "On Technology as Material in Design", "Redstrom", "Vol 3.2"),
    ("03jonasdematerialisation_through_body_orientation.pdf", "Dematerialisation through Body Orientation", "Jonas", "Vol 3.2"),
    ("04ecologies_of_steel.pdf", "Ecologies of Steel", "Fry & Willis", "Vol 3.2"),
    ("02design_waste_and_homelessness.pdf", "Design, Waste and Homelessness", "Loschiavo dos Santos", "Vol 3.3"),
    ("06fryhomelessnessphilosophical_arch.pdf", "Homelessness: a Philosophical Architecture", "Fry", "Vol 3.3"),
    ("03transformation_by_design_or_education.pdf", "The Material Basis of Everyday Rationality", "Christensen", "Vol 3.4"),
    ("04more_actingless_making.pdf", "More Acting & Less Making", "Bousbaci & Findeli", "Vol 3.4"),
    ("05design-and-development.pdf", "Design, Development & Questions of Direction", "Fry", "Vol 3.4"),
    ("02review_of_bruce_sterling_shaping_things.pdf", "Always Historicise Design", "Tonkinwise", "Vol 4.1"),
    ("03reviewlatourharmanverbeek.pdf", "Object-thing Philosophy and Design", "Fry", "Vol 4.1"),
    ("02ontologicaldesigning.pdf", "Ontological Designing", "Willis", "Vol 4.2"),
    ("03designenigmaworldmcneill.pdf", "Design and the Enigma of the World", "McNeill", "Vol 4.2"),
    ("04jonasspecial_moral_code_for_design.pdf", "A Special Moral Code for Design?", "Jonas", "Vol 4.2"),
    ("01frydesign_ethics_and_identity.pdf", "Design, Ethics & Identity", "Fry", "Vol 4.3"),
    ("02designtechnologyethcskockelkorentaylor.pdf", "Design, Technology & Ethics", "Owens", "Vol 4.3"),
    ("03cyborgsingularity_or_sustainment.pdf", "A Cyborg's Choice: Singularity or Sustainment?", "Wahl", "Vol 4.3"),
    ("02blevissustainable_interaction_design.pdf", "Advancing Sustainable Interaction Design", "Blevis", "Vol 4.4"),
    ("02fryredirective_practice.pdf", "Redirective Practice: An Elaboration", "Fry", "Vol 5.1"),
    ("05blevisliving_room_totemunsustainable.pdf", "Living Room Totem of the Unsustainable", "Blevis", "Vol 5.1"),
    ("02forgotten_projectnew_urbanism.pdf", "The Forgotten Project in New Urbanism", "d'Anjou & Weiss", "Vol 5.2"),
    ("04redirective_practiceboonah.pdf", "Redirective Practice in Action", "Fry & Gall", "Vol 5.2"),
    ("05peri_urbanwillis.pdf", "From Peri-urban to Unknown Territory", "Willis", "Vol 5.2"),
    ("02christensen_sustainableservices_flow.pdf", "What is so Sustainable about Services?", "Christensen", "Vol 5.3"),
    ("03danjouexistential_self.pdf", "The Existential Self as Locus of Sustainability", "d'Anjou", "Vol 5.3"),
    ("02liquid_dropdesign_process.pdf", "The Liquid Drop", "Ostlund et al.", "Vol 6.1"),
    ("03stoltermanhci_towardscritical_research.pdf", "HCI: Towards a Critical Research Position", "Stolterman & Fors", "Vol 6.1"),
    ("05philosophicaldialogue.pdf", "Philosophical Dialogue: Everyday Truths?", "McNeill & Christensen", "Vol 6.1"),
    ("06frygap-ability_to_sustain.pdf", "The Gap in the Ability to Sustain", "Fry", "Vol 6.1"),
    ("02redirecting_affective_dispositions-philosophy.pdf", "Redirecting Affective Dispositions", "Christensen", "Vol 6.2"),
    ("03enquist_ecology_of_the_distributed_self.pdf", "A Socio-material Ecology of the Distributed Self", "Enquist", "Vol 6.2"),
    ("04poldmadwelling_futures.pdf", "Dwelling Futures and Lived Experiences", "Poldma", "Vol 6.2"),
    ("01inefficientsustainability.pdf", "Inefficient Sustainability", "Willis & Tonkinwise", "Vol 7.1"),
    ("02stoeklgleaning.pdf", "Gift, Design and Gleaning", "Stoekl", "Vol 7.1"),
    ("03unnatural_capital_bataille_beyond_design.pdf", "Unnatural Capital: Bataille beyond Design", "Hunt", "Vol 7.1"),
    ("04frysustainabilityinsufficiency.pdf", "Sustainability: Inefficiency or Insufficiency?", "Fry", "Vol 7.1"),
    ("05reviewofallan_stoeklbataillepeak.pdf", "Sustainability is not a Humanism", "Tonkinwise", "Vol 7.1"),
    ("02hall-true_cost_button_pushing.pdf", "True Cost Button-pushing", "Hall", "Vol 7.2"),
    ("06unsustainabilitybritish_utility.pdf", "Unsustainability: Towards a New Design History", "Massey & Micklethwaite", "Vol 7.2"),
    ("02barberenvironmentalisation_and_environmentalityarchitecture.pdf", "Environmentalisation: 20thc Architecture Reconceived", "Barber", "Vol 7.3"),
    ("05fam-systemchangesewers.pdf", "Challenge of Systems Change: Sydney's Sewers", "Fam et al.", "Vol 7.3"),
    ("02harriessacredarchitecture.pdf", "On the Need for Sacred Architecture", "Harries", "Vol 8.1"),
    ("04frysacred_designiii.pdf", "Re-turning: Sacred Design III", "Fry", "Vol 8.1"),
    ("06akkachpresence_of_absence.pdf", "The Presence of Absence: Sacred Design Now", "Akkach", "Vol 8.1"),
    ("02shanaagid-social_design-politicalcontexts.pdf", "How Do We Transition People?", "Agid", "Vol 9.3"),
    ("03kiemdesigningsocial-innovation.pdf", "Designing the Social, and Social Innovation", "Kiem", "Vol 9.3"),
    ("02viscommvodeb.pdf", "Beyond the Image and Towards Communication", "Vodeb", "Vol 10.1"),
    ("03design-withoutdesigners.pdf", "Design without Designers", "Raff & Melles", "Vol 10.1"),
    ("06zenhumancentredpractitioner.pdf", "A Way of Being in Design: Zen", "Akama", "Vol 10.1"),
    ("07dwellingdestruction_and_design.pdf", "Home Eco-Nomy: Dwelling, Destruction and Design", "Perolini & Fry", "Vol 10.1"),
    ("02ontologicaldesigmappingwillis.pdf", "The Ontological Designing of Mapping", "Willis", "Vol 10.2"),
    ("02keshavarzdissensus.pdf", "Design and Dissensus", "Keshavarz & Maze", "Vol 11.1"),
    ("03kiemreviewdisalvoadversarialdesign.pdf", "If Political Design Changed Anything", "Kiem", "Vol 11.1"),
    ("06serviceinterfacephilipsdirectlife.pdf", "Thinking through the Service Interface", "Secomandi", "Vol 11.1"),
    ("1fryorigin-work_of_design.pdf", "The Origin of the Work of Design", "Fry", "Vol 12.1"),
    ("2townsendcomplexity_and_control.pdf", "Complexity and Control", "Townsend", "Vol 12.1"),
    ("3ghassanearth_with_agency.pdf", "Earth with Agency: A Thoroughly Queer Notion", "Ghassan", "Vol 12.1"),
    ("5boano-agambenurbandesign.pdf", "Agamben's Gesture of Profanation", "Boano & Talocci", "Vol 12.1"),
    ("1kalantidoufuture_of_athens.pdf", "Westernizing the Semi-Orient", "Kalantidou", "Vol 12.2"),
    ("2boehnertdesign_industry.pdf", "Design vs. the Design Industry", "Boehnert", "Vol 12.2"),
    ("4willisdesignbackfuture.pdf", "Designing Back from the Future", "Willis", "Vol 12.2"),
    ("6tonkinwisedunne-raby.pdf", "How We Intend to Future", "Tonkinwise", "Vol 12.2"),
    ("2escobartransiciones.pdf", "Transiciones", "Escobar", "Vol 13.1"),
    ("1irwin-et-alprovocation.pdf", "Transition Design Provocation", "Irwin, Kossoff & Tonkinwise", "Vol 13.1"),
    ("3kossoff-holism.pdf", "Holism and the Reconstitution of Everyday Life", "Kossoff", "Vol 13.1"),
    ("4damianwhitemetaphorshrybridity.pdf", "Metaphors, Hybridity, Failure and Work", "White", "Vol 13.1"),
    ("8willis-refusediscipline.pdf", "Transition Design: Refuse Discipline", "Willis", "Vol 13.1"),
    ("10tonkinwisefrom_and_to_what.pdf", "Design for Transitions - from and to what?", "Tonkinwise", "Vol 13.1"),
    ("1keshavarzmaterial_practices1-passporting.pdf", "Material Practices of Power I", "Keshavarz", "Vol 13.2"),
    ("2dilnot-the_matter_of_design.pdf", "The Matter of Design", "Dilnot", "Vol 13.2"),
    ("3ventura-uncannymechanics.pdf", "Uncanny Mechanics", "Ventura", "Vol 13.2"),
    ("1keshavarzmaterial_practices-of-power2.pdf", "Material Practices of Power II", "Keshavarz", "Vol 14.1"),
    ("4ghassan-designer_as_minor_scientist.pdf", "Fluidity and Legitimacy: Designer as Minor Scientist", "Ghassan & Blythe", "Vol 14.1"),
    ("01designglobalsoutheditorial.pdf", "Editorial: Design and the Global South", "Fry & Willis", "Vol 15.1"),
    ("02frypositionpaper.pdf", "Design for/by The Global South", "Fry", "Vol 15.1"),
    ("03arturoescobar.pdf", "Response: Design for/by the Global South", "Escobar", "Vol 15.1"),
    ("04madinatlostanovadecolonizingdesign.pdf", "On Decolonizing Design", "Tlostanova", "Vol 15.1"),
    ("05hernan-daniel-alterdesign.pdf", "Alter Design", "Lopez-Garay & Lopera Molano", "Vol 15.1"),
    ("08vazquezprecedenceearthanthropocene.pdf", "Precedence, Earth and the Anthropocene", "Vazquez", "Vol 15.1"),
    ("02designafterdesign.pdf", "Design After Design", "Fry", "Vol 15.2"),
    ("03materialcntrldigitalfabrication.pdf", "Material Control: Digital Fabrication", "McMeel", "Vol 15.2"),
    ("05design-aestheticexperience_.pdf", "Design and Contemporary Aesthetic Experiences", "Folkmann & Jensen", "Vol 15.2"),
    ("06designknowledgehumaninterest.pdf", "Design, Knowledge and Human Interest", "Dilnot", "Vol 15.2"),
]


def download():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    total = len(PAPERS)
    downloaded = 0
    skipped = 0
    failed = []

    print(f"Downloading {total} papers to ./{OUTPUT_DIR}/\n")

    for i, (filename, title, author, vol) in enumerate(PAPERS, 1):
        dest = os.path.join(OUTPUT_DIR, filename)

        # Skip if already downloaded
        if os.path.exists(dest) and os.path.getsize(dest) > 1000:
            print(f"  [{i:3}/{total}] skip  {filename}")
            skipped += 1
            continue

        url = BASE_URL + filename
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()

            # Basic sanity check - PDFs start with %PDF
            if not data.startswith(b'%PDF'):
                raise ValueError(f"Response doesn't look like a PDF (got: {data[:20]})")

            with open(dest, 'wb') as f:
                f.write(data)

            size_kb = len(data) // 1024
            print(f"  [{i:3}/{total}] ok    {filename}  ({size_kb} KB)")
            downloaded += 1

        except Exception as e:
            print(f"  [{i:3}/{total}] FAIL  {filename}  — {e}")
            failed.append((filename, str(e)))

        time.sleep(DELAY)

    # Summary
    print(f"\n--- Done ---")
    print(f"Downloaded: {downloaded}")
    print(f"Skipped (already existed): {skipped}")
    print(f"Failed: {len(failed)}")

    if failed:
        print("\nFailed files:")
        for filename, reason in failed:
            print(f"  {filename}: {reason}")

    print(f"\nPDFs saved to: {os.path.abspath(OUTPUT_DIR)}/")


if __name__ == "__main__":
    download()
