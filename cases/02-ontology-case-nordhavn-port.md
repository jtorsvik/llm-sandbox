# Case 2: Nordhavn Port ontology (ontology modelling)

> Fictive case. Built for learning how to design an ontology, from competency questions to OWL/RDF, validation and querying. It is independent from Case 1, but see the last section for how they can be combined.

## Background

**Nordhavn Port** is a mid-sized Norwegian port handling container ships, ferries, bulk cargo and fishing vessels. After two mergers, it runs five systems that all describe "the same things" differently:

| System | Owner | What it calls things |
|---|---|---|
| **PortOps** (berth planning) | Operations | `Vessel`, `Berth`, `Call` (a ship visiting) |
| **CargoTrack** | Logistics | `Unit`, `Consignment`, `Vessel_Name` as free text |
| **CustomsLink** | Customs liaison | `Declaration`, `Carrier`, `IMO` |
| **SafetyLog** | HSE | `Incident`, `Area`, `Equipment` |
| **Maintenance** | Technical | `Asset`, `WorkOrder`, `Location` |

## The problem

Nobody can answer cross-system questions without a week of manual work. Examples:

1. "Which dangerous-goods containers were on vessels that berthed at a quay where a safety incident occurred in the last 30 days?"
2. "Which cranes are overdue for maintenance and are needed for vessels arriving in the next 48 hours?"
3. "If berth 4 is closed, which scheduled calls are affected and which consignments are on them?"
4. "Is every vessel carrying dangerous goods covered by a customs declaration?"

The data lake team's attempt at a "master table" failed because the same word means different things in different systems.

## Your assignment

Design and build an **ontology** that gives the five systems a shared, machine-readable vocabulary, and demonstrate that it can answer the four questions above.

## Where the meanings clash (the heart of the case)

| Term | PortOps | CargoTrack | SafetyLog | Maintenance |
|---|---|---|---|---|
| "Location" | A berth | A yard slot | A named area (may be a zone covering several berths) | A GPS point for an asset |
| "Vessel" | Identified by IMO, one record per ship | Free-text name, misspelled | Not tracked, only "ship involved" | Not applicable |
| "Call" / "Visit" | One arrival and departure | A voyage number that may span several calls | Not tracked | Not tracked |
| "Equipment" | Berth cranes only | Reefer plugs, trailers | Anything that can cause an incident | All assets, including buildings |
| "Dangerous goods" | Yes/No flag | UN number + class | Incident type | Not tracked |

Decide which of these are:
- the **same concept** under different names (synonyms, map them)
- **different concepts** sharing a name (split them)
- **one concept at different granularity** (use subclass or part-of)

## Sample source data (mock these as CSV)

```csv
# portops_calls.csv
call_id,imo,vessel_name,berth,eta,etd,status
C-2026-1187,9321483,MV Nordic Hope,Q4,2026-10-16T06:00,2026-10-17T14:00,scheduled
C-2026-1188,9455211,MS Fjordkongen,Q2,2026-10-16T09:30,2026-10-16T21:00,scheduled

# cargotrack_units.csv
unit_id,vessel_name,voyage_no,un_number,imdg_class,yard_slot,consignee
MSKU7712345,Nordic Hope,NH-441,1203,3,Y-12-3,Bergen Drivstoff AS
TGHU9981234,Nordic hope ,NH-441,,,Y-14-1,Aker Kjøkken AS

# safetylog_incidents.csv
incident_id,date,area,type,severity,ship_involved,equipment_id
INC-0932,2026-10-02,Quay Zone North,fuel_spill,medium,,TRK-07
INC-0933,2026-10-09,Quay Zone North,crane_near_miss,high,Nordic Hope,CR-04

# maintenance_assets.csv
asset_id,type,location_gps,next_service_due,status
CR-04,quay_crane,"60.3941,5.3201",2026-10-10,overdue
CR-05,quay_crane,"60.3943,5.3215",2026-11-20,ok
```

Note the planted problems: a vessel name spelled three ways, a missing UN number, an area ("Quay Zone North") that covers berths Q3 and Q4, and a crane that is overdue.

## Learning goals

- Start from **questions**, not from data (competency questions)
- Distinguish classes, individuals, object properties, data properties and constraints
- Know when to use subclass, part-of, role or state, and when not to
- Handle identity: how do you know two records are the same ship?
- Express rules (open world versus closed world, and why SHACL exists next to OWL)
- Map messy source data onto the ontology and query it with SPARQL
- Evaluate the ontology: can it answer the questions, and is it consistent?

## Milestones

### M1: Competency questions
Write 15 to 20 questions in plain language, group them by stakeholder, and rank by value. The four above are a start. The ontology scope is *"what is needed to answer these"*, nothing more.

### M2: Glossary and conceptual model
Extract nouns and verbs from the questions and the source columns. Make a glossary with a definition per term, then sketch classes and relations on paper or in a diagram (draw.io, Mermaid). Resolve the term clashes from the table above and **write down why** for each decision.

### M3: Formal ontology
Implement it in OWL using Turtle. Tools: `rdflib` and `owlready2` in Python, or Protégé as a GUI.

A minimal starting point to expand on:

```turtle
@prefix nh:   <https://example.org/nordhavn#> .
@prefix owl:  <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .

nh:Vessel        a owl:Class .
nh:PortCall      a owl:Class .
nh:Berth         a owl:Class .
nh:QuayCrane     a owl:Class ; rdfs:subClassOf nh:Asset .

nh:forVessel     a owl:ObjectProperty ; rdfs:domain nh:PortCall ; rdfs:range nh:Vessel .
nh:atBerth       a owl:ObjectProperty ; rdfs:domain nh:PortCall ; rdfs:range nh:Berth .
nh:imoNumber     a owl:DatatypeProperty, owl:FunctionalProperty ;
                 rdfs:domain nh:Vessel ; rdfs:range xsd:string .
```

Think about: Is a "dangerous goods unit" a subclass of Unit, or a Unit with a property? Is "overdue" a class, a state or a computed fact? Is `Area` part of a `Berth` or the other way around?

### M4: Populate (mapping)
Write a Python script that converts the four CSV files into RDF triples using your ontology (a hand-written mapping, or R2RML/`rdflib`). Solve identity: normalise `"Nordic hope "` and `"MV Nordic Hope"` to one `nh:Vessel` with IMO `9321483`.

### M5: Query
Answer the four questions with SPARQL. Example skeleton for question 2:

```sparql
PREFIX nh: <https://example.org/nordhavn#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
SELECT ?crane ?call WHERE {
  ?crane a nh:QuayCrane ; nh:maintenanceStatus nh:Overdue .
  ?call  a nh:PortCall ; nh:requiresEquipment ?crane ;
         nh:eta ?eta .
  FILTER (?eta < "2026-10-17T13:00:00"^^xsd:dateTime)
}
```

If a question can't be answered, decide whether the **ontology** or the **data** is wrong.

### M6: Validation
- Run a reasoner (HermiT or Pellet through `owlready2`) and fix inconsistencies
- Add **SHACL** shapes (`pyshacl`) for rules such as: every `PortCall` has exactly one vessel, every dangerous-goods unit has a UN number, ETD is after ETA
- Explain to yourself why the missing UN number is not caught by OWL (open world) but is caught by SHACL (closed world)

### M7: Evolve it
New requirement arrives: *"We now handle LNG bunkering."* Extend the ontology **without breaking** existing queries. Record what you had to change and why.

## Acceptance criteria

- [ ] All four example questions answered via SPARQL with correct results on the sample data
- [ ] Every class and property has a label and a definition (`rdfs:label`, `skos:definition`)
- [ ] The three vessel spellings resolve to one individual
- [ ] SHACL catches the unit with the missing UN number
- [ ] A one-page decision log explains how each term clash was resolved
- [ ] The ontology loads without errors in Protégé

## Stretch ideas

- Reuse existing vocabularies instead of inventing everything: `time:` (OWL-Time), `geo:` (GeoSPARQL), `skos:`, `prov:`
- Add provenance: which source system said what, and when
- Load the data into a triple store (Apache Jena Fuseki, or Oxigraph) instead of in-memory rdflib
- Compare with a **property graph** (Neo4j) for the same questions. When is each better?

## Combining with LLMs (optional, ties into Case 1)

Once the ontology works, try:

1. **Ontology-assisted extraction**: let an LLM read free-text incident reports and output triples that conform to your ontology, then validate with SHACL
2. **Text-to-SPARQL agent**: give a LangGraph agent the ontology schema and let it translate "which cranes are overdue?" into SPARQL, execute it, and explain the result. Evaluate it on your competency questions
3. **LLM as modelling assistant**: ask an LLM to propose classes from the glossary, then critique its suggestions against your own decisions in M2

A good ontology makes agents more reliable, because it gives them a precise vocabulary to work with.

## Suggested tooling

```bash
uv add rdflib owlready2 pyshacl
```

Folder idea: `llm-sandbox/src/nordhavn/{data,ontology,mapping,queries,shapes}/`.
