<!-- SPDX-License-Identifier: MIT -->

# Facet register, general scope

The general scope's facet values, which every installation of Вивід has. A knowledge base's general scope, a domain or a project extends them with values of its own. From LATTICE's facet register, relicensed MIT by its author.

## Schemes

| ID | Label | Definition |
|---|---|---|
| Activity | activity | What the person or agent is doing when the entry matters. A skill loaded for a task supplies it. |
| Quality | quality | The characteristic an entry protects, or trades against another. |
| Technology | technology | The technology an entry is specific to. An entry true of any technology carries none. |

## Activity

| ID | Label | Broader | Related | Group | Definition | Scope note | Ratified |
|---|---|---|---|---|---|---|---|
| analysis | analysis |  |  | yes | Working out what is needed and what is true of the domain, before anything is built. |  | yes |
| architecture | architecture |  |  | yes | Deciding a system's structure, its parts and how they couple, and the qualities it must have. |  | yes |
| design | design |  |  | yes | Any of the design activities, from a single layer to a whole solution. |  | yes |
| data-management | data management |  |  | yes | Governing, integrating and looking after data over its life, as DAMA-DMBOK divides the field. |  | yes |
| coding | coding |  |  | yes | Turning a design into working code, queries and configuration. |  | yes |
| verification | verification and validation |  |  | yes | Showing that what was built is right, and is what was needed. |  | yes |
| operations | operations |  |  | yes | Building, deploying, running and supporting software once it exists, the DevOps loop. |  | yes |
| security-engineering | security engineering |  |  | yes | Designing, building and running so that misuse fails and a breach is contained. |  | yes |
| delivery-management | delivery management |  |  | yes | Planning, sequencing and governing the work itself. |  | yes |
| technical-writing | technical writing |  |  | yes | Writing and presenting what others need to read, such as guides, references, decisions and diagrams. |  | yes |
| requirements-analysis | requirements analysis | analysis |  |  | Working out what a stakeholder, a regulation, a contract or the law needs, before anything is designed. |  | yes |
| requirements-elicitation | requirements elicitation | requirements-analysis |  |  | Drawing needs out of stakeholders, documents and regulations. |  | yes |
| requirements-specification | requirements specification | requirements-analysis |  |  | Writing requirements down so they can be checked, with their acceptance criteria. |  | yes |
| domain-analysis | domain analysis | analysis |  |  | Learning a domain's concepts, rules and vocabulary from its experts and texts, including how the law and contract drafting answer a question. |  | yes |
| regulatory-analysis | regulatory analysis | analysis | regulatory-compliance |  | Working out what a law, regulation or standard requires of a system or its data. |  | yes |
| business-process-analysis | business process analysis | analysis |  |  | Studying how work is done today, with its roles, steps and hand-offs, before redesigning it. |  | yes |
| feasibility-analysis | feasibility analysis | analysis |  |  | Testing whether an approach can work at acceptable cost before committing to it, by a spike, a prototype or a measurement. |  | yes |
| cross-layer-design | cross-layer design | architecture design |  |  | Deciding which layer or module a concept belongs in, and what each may depend on. |  | yes |
| enterprise-architecture | enterprise architecture | architecture |  |  | Relating business, data, application and technology architecture across an organisation, as TOGAF divides it. |  | yes |
| solution-architecture | solution architecture | architecture |  |  | Shaping the components, deployments and integrations of one solution, and the qualities each must meet. |  | yes |
| architecture-decision-making | architecture decision-making | architecture |  |  | Framing an architecturally significant choice, comparing the options on their consequences, and recording it as an ADR. |  | yes |
| quality-attribute-analysis | quality attribute analysis | architecture |  |  | Setting the qualities a system must have, with their scenarios and measures, and the trade-offs between them. |  | yes |
| technology-selection | technology selection | architecture |  |  | Choosing a language, store, library, platform or service, including its licence and the cost of leaving it. |  | yes |
| dependency-analysis | dependency and coupling analysis | architecture |  |  | Tracing which parts depend on which, and what must change and release together. |  | yes |
| fitness-function-design | fitness function design | architecture verification |  |  | Designing the checks that keep an architectural characteristic from eroding, atomic or holistic, triggered or continual. |  | yes |
| process-design | process design | design |  |  | Designing how work, messages or decisions pass between participants over time. |  | yes |
| solution-design | solution design | design | physical-data-modelling |  | Designing a component, service, compiler or library that executes against the ontologies, including how it stores and reads data. | Use for the design of a component as a whole. Use physical data modelling for how it lays out and writes its data, and identity design for how it names things. | yes |
| integration-design | integration design | design |  |  | Designing how data or messages move between systems, formats or stores, inbound or outbound. |  | yes |
| api-and-contract-design | API and contract design | coding design |  |  | Designing a wire contract, a schema, a recipe format or a programming interface that others call. |  | yes |
| ux-design | UX design | design | interaction-capability |  | Designing what a person sees and does in an application or an add-in. |  | yes |
| data-modelling | data modelling | design |  |  | Designing the structure, meaning and constraints of data, at the conceptual, logical or physical level. |  | yes |
| conceptual-data-modelling | conceptual data modelling | data-modelling |  |  | Naming the things, relations and rules of a domain without regard to how they are stored. |  | yes |
| logical-data-modelling | logical data modelling | data-modelling |  |  | Giving a conceptual model keys, cardinalities, constraints and shapes, independent of any one store. |  | yes |
| physical-data-modelling | physical data modelling | data-modelling |  |  | Fitting a logical model to a store, with its indexes, partitions, graphs, encodings and write paths. | Use for how a model is laid out in a store and written to it, such as aggregates, guarded writes and history. Use solution design for the component around it. | yes |
| ontology-design | ontology design | conceptual-data-modelling design logical-data-modelling |  |  | Designing classes, properties, shapes and vocabularies within one layer or applied module. | Use for authoring an ontology as well as designing one, including any change under `ontology/`. The skill `lattice-ontology-authoring` and the plans call this activity authoring, and `ontology-authoring` is not a value. Use cross-layer design for deciding which layer a concept belongs in. | yes |
| schema-design | schema design | api-and-contract-design logical-data-modelling |  |  | Designing a schema others validate against, such as a SHACL shape, a JSON Schema or a table definition. |  | yes |
| identity-design | identity design | data-modelling |  |  | Deciding how things are identified, keyed and versioned, and how their identifiers are minted. |  | yes |
| temporal-modelling | temporal modelling | data-modelling |  |  | Modelling validity periods, recording time, history, versions and as-of reads. |  | yes |
| event-and-message-design | event and message design | design integration-design |  |  | Designing the events and messages systems exchange, with their schemas, ordering and delivery guarantees. |  | yes |
| algorithm-design | algorithm design | coding design |  |  | Designing a procedure and its complexity, such as an evaluator, a resolution rule or a compiler pass. |  | yes |
| language-design | language and compiler design | design |  |  | Designing a notation, its grammar and semantics, and the compiler or interpreter that reads it. |  | yes |
| data-governance | data governance | data-management |  |  | Deciding who owns, may change and must approve data and vocabularies, and under what policy. |  | yes |
| metadata-management | metadata management | data-management |  |  | Recording what data means, where it came from and how it moved, including its lineage. |  | yes |
| reference-and-master-data | reference and master data | data-management |  |  | Managing the shared code lists, vocabularies and golden records that many systems depend on. |  | yes |
| data-quality-management | data quality management | data-management | data-quality |  | Measuring and improving data against its quality dimensions, with the rules that test them. |  | yes |
| data-integration | data integration | data-management integration-design |  |  | Moving and reconciling data between sources, by mapping, transformation and lifting into a common model. |  | yes |
| data-migration | data migration | data-management |  |  | Moving data from one model or store to another, and proving nothing was lost or changed in meaning. |  | yes |
| data-lifecycle | data retention and archiving | data-management |  |  | Deciding how long data is kept, when it is pruned or archived, and how it is erased. |  | yes |
| analytics-and-reporting | analytics and reporting | data-management |  |  | Deriving measures, aggregates and reports from data, including warehousing and business intelligence. |  | yes |
| document-management | document and content management | data-management |  |  | Managing documents, their versions, wording and attachments as records. |  | yes |
| implementation | implementation | coding | code-generation |  | Writing or changing code. | Use for code written by hand. Use code generation where the code writes code, queries or documents, and language design for the notation such code reads. | yes |
| query-writing | query writing | coding |  |  | Writing or tuning SPARQL, a SHACL-SPARQL constraint or a query a compiler generates. |  | yes |
| refactoring | refactoring | coding |  |  | Changing code's structure without changing what it does. |  | yes |
| debugging | debugging | coding |  |  | Finding and fixing the cause of a defect, from its symptom to its root. |  | yes |
| code-review | code review | coding verification |  |  | Reading a change for defects, design and conformance before it merges. |  | yes |
| dependency-management | dependency management | coding |  |  | Adding, pinning, upgrading and removing the libraries and tools a codebase depends on. |  | yes |
| performance-tuning | performance tuning | coding | efficiency performance-efficiency |  | Measuring where time or memory goes and removing it, without changing results. |  | yes |
| code-generation | code generation | coding |  |  | Writing the generators, templates and compilers that emit code, queries or documents. | Use for generators, templates and compilers, and the code they emit. Use implementation for code written by hand. | yes |
| testing | testing | verification |  |  | Writing, running, speeding up or repairing tests, checks and benchmarks. | Use where none of its kinds fits. A rule about a check's own power to catch a fault takes testing with the quality testability. | yes |
| unit-testing | unit testing | testing |  |  | Testing one function, class or module apart from the rest. |  | yes |
| integration-testing | integration testing | testing |  |  | Testing parts together, such as code against a real store or service. |  | yes |
| end-to-end-testing | end-to-end testing | testing |  |  | Testing a whole flow the way a user or caller drives it. |  | yes |
| conformance-testing | conformance testing | testing |  |  | Testing an implementation against a specification or a shared set of vectors, so several implementations agree. |  | yes |
| property-based-testing | property-based testing | testing |  |  | Testing a stated property over generated inputs rather than chosen examples. |  | yes |
| regression-testing | regression testing | testing |  |  | Recording what a system reports and checking that a change leaves it as it was. | Use for record and replay, and for comparing outcomes before and after a change. | yes |
| performance-testing | performance testing | testing | performance-efficiency |  | Measuring time, memory or throughput under a stated load, including benchmarks. |  | yes |
| security-testing | security testing | security-engineering testing | security |  | Testing for vulnerabilities, by scanning, fuzzing or penetration. |  | yes |
| scenario-and-test-data | scenarios and test data | testing verification |  |  | Writing the examples, fixtures and scenarios a model or a test must accept or refuse. |  | yes |
| formal-verification | formal verification | verification |  |  | Stating laws and proving or bound-checking them in a prover or model checker. |  | yes |
| static-analysis | static analysis | verification |  |  | Checking code or models without running them, such as linting, type checking and dependency rules. |  | yes |
| acceptance | acceptance | verification |  |  | Confirming with stakeholders that what was built meets the need, at a gate. |  | yes |
| environment | environment | operations |  |  | Setting up, running or repairing the toolchain, the tasks and the local services a developer works with. |  | yes |
| build-automation | build automation | operations |  |  | Compiling, packaging and assembling software reproducibly. |  | yes |
| continuous-integration | continuous integration | operations |  |  | Merging and checking every change automatically and often. |  | yes |
| continuous-delivery | continuous delivery | operations |  |  | Keeping every change releasable, and moving it through environments automatically. |  | yes |
| deployment | deployment | operations |  |  | Putting a release onto its runtime with its configuration, and rolling it back. |  | yes |
| infrastructure-as-code | infrastructure as code | operations |  |  | Declaring infrastructure and environments in versioned files that a tool applies. |  | yes |
| configuration-management | configuration management | operations |  |  | Controlling which versions of software, configuration and data make up a system. |  | yes |
| release-and-versioning | release and versioning | configuration-management delivery-management operations |  |  | Versioning, releasing and tagging ontologies and packages, and the branches and merges a release moves through. | Use for version numbers, tags and releases. Use delivery for the rest of running a unit of work. | yes |
| monitoring | monitoring and observability | operations | observability |  | Collecting and reading metrics, logs and traces so a running system's state is known. |  | yes |
| incident-response | incident response | operations security-engineering |  |  | Detecting, containing and resolving an outage or a breach, and learning from it. |  | yes |
| backup-and-recovery | backup and recovery | operations | recoverability |  | Keeping copies that let a system be restored, and rehearsing the restore. |  | yes |
| capacity-planning | capacity planning | operations | scalability |  | Forecasting load and sizing resources to meet it. |  | yes |
| platform-engineering | platform engineering | operations |  |  | Building the shared tooling, templates and services other teams build and run on. |  | yes |
| threat-modelling | threat modelling | security-engineering | security |  | Naming what could be attacked, by whom and how, and what stops it. |  | yes |
| identity-and-access-design | identity and access design | design security-engineering |  |  | Designing authentication, authorisation, roles and the scope of what each caller may reach. |  | yes |
| secrets-management | secrets management | security-engineering |  |  | Storing, rotating and injecting credentials and keys so none reach code, logs or commits. |  | yes |
| cryptography-design | cryptography design | security-engineering |  |  | Choosing and applying hashing, signing and encryption correctly. |  | yes |
| supply-chain-security | supply chain security | security-engineering |  |  | Trusting what software is built from, its dependencies, tools and images, by pinning, provenance and verification. |  | yes |
| vulnerability-management | vulnerability management | security-engineering |  |  | Finding, triaging and fixing known weaknesses in code and dependencies. |  | yes |
| privacy-engineering | privacy engineering | security-engineering | privacy |  | Building data protection in, by minimisation, purpose limits, consent and erasure. |  | yes |
| compliance-assessment | compliance assessment | security-engineering verification |  |  | Showing that a system meets a standard, a regulation or a licence, with evidence. |  | yes |
| delivery | delivery | delivery-management |  |  | Running a unit of work, with its slices, plans, status records, Validation Packs, handoffs and commits, and knowing when to stop for a decision. | Use for running a unit of work. Use release and versioning for version numbers and tags, and continuous integration for automated checks. | yes |
| planning-and-estimation | planning and estimation | delivery-management |  |  | Breaking work down, sequencing it and estimating its cost. |  | yes |
| risk-management | risk management | delivery-management |  |  | Naming what could go wrong with the work or the system, and deciding what to do about it. |  | yes |
| technical-debt-management | technical debt management | delivery-management |  |  | Recording, weighing and paying down known shortfalls. |  | yes |
| licensing-and-ip | licensing and intellectual property | delivery-management | licence-compliance |  | Deciding which licence governs a contribution, and what may be used, published or distributed. |  | yes |
| documentation | documentation | technical-writing | understandability |  | Writing READMEs, guides, ADRs, sketches and other prose others read, and deciding what of it may be published. | Use for writing prose others read. Name the quality it serves as readability or understandability. | yes |
| presenting-decisions | presenting decisions | technical-writing |  |  | Laying out a decision's options and consequences for someone else to choose between. |  | yes |
| diagramming | diagramming | technical-writing |  |  | Drawing the views, flows and states that explain a design. |  | yes |
| onboarding | training and onboarding | technical-writing |  |  | Teaching others to use or contribute, through guides, examples and walk-throughs. |  | yes |

## Quality

| ID | Label | Broader | Related | Group | Definition | Scope note | Ratified |
|---|---|---|---|---|---|---|---|
| functional-suitability | functional suitability |  |  | yes | Whether it does what is needed, completely, correctly and appropriately. |  | yes |
| performance-efficiency | performance efficiency |  |  | yes | How it uses time and resources, and how much it can take. |  | yes |
| compatibility | compatibility |  |  | yes | Working beside, and together with, other systems. |  | yes |
| interaction-capability | interaction capability |  |  | yes | How well people can use it. |  | yes |
| reliability | reliability |  |  | yes | Doing the right thing over time, despite faults. |  | yes |
| maintainability | maintainability |  |  | yes | How easily it can be understood, tested and changed. |  | yes |
| flexibility | flexibility |  |  | yes | How easily it adapts to new conditions, loads and environments. |  | yes |
| safety | safety |  |  | yes | Avoiding harm to people, property or the environment. |  | yes |
| data-quality | data quality |  |  | yes | The qualities of data itself, as ISO/IEC 25012 divides them. |  | yes |
| cost | cost |  |  | yes | What it costs to build and to run. |  | yes |
| governance-and-compliance | governance and compliance |  |  | yes | Meeting obligations, and being able to show that they were met. |  | yes |
| correctness | correctness | functional-suitability | accuracy |  | A query, check, evaluation or document gives the answer the model's meaning requires. | Use where the answer follows from the model's own meaning, such as an evaluation or a query result. Use accuracy where a model or a report must represent something real truly. | yes |
| completeness | completeness | data-quality functional-suitability |  |  | Nothing needed is missing, whether a function or a value. |  | yes |
| appropriateness | appropriateness | functional-suitability |  |  | It does what the user's goal needs, and nothing that gets in the way of it. |  | yes |
| determinism | determinism | functional-suitability robustness |  |  | The same input gives the same output, whatever the order, the hash seed, the clock or the implementation. |  | yes |
| performance | performance | performance-efficiency |  |  | How long one operation takes at runtime, such as a read on a hot path or a validation. | Use for how long one operation of the running system takes. Use efficiency for the speed of builds and tests, and throughput for work completed under load. | yes |
| throughput | throughput | performance-efficiency |  |  | How much work completes per unit of time under load. |  | yes |
| storage | storage | performance-efficiency |  |  | How much is stored per write, per entity or per version, and for how long. |  | yes |
| parallelism | parallelism | functional-suitability performance-efficiency |  |  | Work split across cores, processes or workers stays correct, and gets faster as workers are added up to a measured limit. The twin of concurrency. |  | yes |
| memory | memory | performance-efficiency |  |  | How much memory an operation or a process holds at its peak. |  | yes |
| scalability | scalability | flexibility performance-efficiency |  |  | How a cost grows as data, history, writers or entries grow. |  | yes |
| interoperability | interoperability | compatibility |  |  | Exchanging data or calls with another system, and both reading them the same way. |  | yes |
| co-existence | co-existence | compatibility |  |  | Running beside other software on a shared host or store without harming it. |  | yes |
| standards-conformance | standards conformance | compatibility |  |  | Following the published standard a consumer expects, such as SPARQL 1.1 or SHACL. |  | yes |
| accessibility | accessibility | interaction-capability |  |  | People with disabilities can use what is built, in an application or a document. |  | yes |
| learnability | learnability | interaction-capability |  |  | How quickly a new user or contributor becomes productive. |  | yes |
| operability | operability | interaction-capability |  |  | How easily a person operates and controls it. |  | yes |
| user-error-protection | user error protection | interaction-capability |  |  | Protecting a user from making a mistake, and from its consequences. |  | yes |
| self-descriptiveness | self-descriptiveness | interaction-capability understandability |  |  | It explains itself by its names, messages and documentation, without outside help. |  | yes |
| availability | availability | reliability | partition-tolerance replica-consistency |  | Being there when needed, measured as uptime. |  | yes |
| robustness | robustness | reliability |  |  | Behaving well on failure, such as a partial write, a retry, a restore, missing data or bad input. | Use for behaving well on failure or bad input. Use recoverability for returning to a correct state after a failure. | yes |
| recoverability | recoverability | reliability |  |  | Returning to a correct state after a failure, knowing what was lost. |  | yes |
| concurrency | concurrency | functional-suitability reliability | integrity parallelism |  | Staying correct when writers or readers act at the same time. | Use for staying correct while writers or readers act at once, such as a lost update. Use parallelism for splitting work so it runs faster. | yes |
| partition-tolerance | partition tolerance | reliability | replica-consistency |  | It keeps working when the network between its parts fails. One of the three properties of the CAP theorem, which a distributed system trades against the other two. |  | yes |
| replica-consistency | replica consistency | reliability |  |  | Every read sees the latest write, across every copy or replica. One of the three properties of the CAP theorem, and distinct from consistency between records. | Use only where copies or replicas of data exist, such as an eventually consistent tier. Use consistency for agreement between the records of one store. | yes |
| security | security |  |  |  | Resisting misuse, such as an injected query, a forged or replayed request, or code reaching a store it should not. |  | yes |
| confidentiality | confidentiality | security |  |  | What must not be disclosed stays undisclosed, such as personal data, secrets, private material and a person's own setup. |  | yes |
| integrity | integrity | security |  |  | Data and code cannot be changed without authority, and a change is detectable. | Use for protection against change without authority, including a lost, stale or forged write. Use consistency for agreement between records. | yes |
| authenticity | authenticity | security |  |  | Who or what an actor claims to be can be proved. |  | yes |
| accountability | accountability | security |  |  | Every action can be traced to whoever took it. |  | yes |
| non-repudiation | non-repudiation | security |  |  | An action, once taken, cannot later be denied. |  | yes |
| privacy | privacy | governance-and-compliance security |  |  | Personal data is collected, used and kept only as its purpose and the law allow. |  | yes |
| evolvability | evolvability | flexibility maintainability | modularity |  | Changing something later safely, which turns on versions, compatibility, coupling and what a change forces elsewhere. | Use for change over time, such as versions, compatibility and what a change forces elsewhere. Use modularity for coupling between parts. | yes |
| modularity | modularity | maintainability |  |  | Parts can change apart, because they are loosely coupled and each is cohesive. | Use for coupling and dependency between parts, such as a layer that must not import a layer above it. Use evolvability for versions and compatibility. | yes |
| reusability | reusability | maintainability |  |  | A part can serve more than one system or purpose. |  | yes |
| understandability | understandability | maintainability |  |  | A human or AI reader can tell what a thing is and means, whether an element in code, a term in a document or a concept in a model. |  | yes |
| naming-conventions | naming conventions | understandability |  |  | Things are named by a rule and by the terms the project already uses, so a name says what it refers to. |  | yes |
| consistent-terminology | consistent terminology | understandability |  |  | A term means one thing wherever it appears, in code, documents and models, and one thing has one term. |  | yes |
| concept-definition | concept definition | understandability |  |  | Each concept is defined once, where it lives, in words that do not need the reader to know its implementation. |  | yes |
| readability | readability | understandability |  |  | Code and prose can be read and followed quickly, by their structure, layout and length. |  | yes |
| analysability | analysability | maintainability |  |  | The effect of a change, or the cause of a failure, can be worked out. |  | yes |
| testability | testability | maintainability |  |  | It can be tested well, with clear criteria and inputs a test controls. |  | yes |
| observability | observability | maintainability reliability |  |  | A running system's internal state can be inferred from what it emits. |  | yes |
| portability | portability | flexibility |  |  | Working on every operating system, engine, store or host a consumer may use. |  | yes |
| installability | installability | flexibility |  |  | It can be installed, upgraded and removed reliably. |  | yes |
| replaceability | replaceability | flexibility |  |  | It can be swapped for another part that does the same job. |  | yes |
| configurability | configurability | flexibility |  |  | Behaviour changes by configuration rather than by code. |  | yes |
| fail-safety | fail-safety | safety |  |  | Hazards are identified, warned of and contained, and a failure leaves things safe. |  | yes |
| consistency | consistency | data-quality |  |  | Records and documents agree with each other. One fact has one source, and copies cannot diverge. | Use where one fact must have one record that copies cannot contradict. Use replica consistency for reads across copies, concurrency for simultaneous writers, and integrity for change only by authority. | yes |
| accuracy | accuracy | data-quality |  |  | A value correctly represents the real thing it stands for. | Use where a model, a report or a value must truly represent the real thing, such as modelling the law or reporting a check's result. Use correctness for what follows from the model's own meaning. | yes |
| currentness | currentness | data-quality |  |  | A value is as up to date as its use needs. |  | yes |
| precision | precision | data-quality |  |  | A value carries as much detail as its use needs, and states the detail it has. |  | yes |
| provenance | provenance | data-quality governance-and-compliance |  |  | Where a value came from, who asserted it and how it was derived is recorded. |  | yes |
| efficiency | efficiency | cost |  |  | What development costs, such as the time of builds and tests, the tokens and reading an agent spends, and the maintainer's effort. Runtime speed is performance. | Use for what development costs, such as the speed of builds and test suites. Use performance for how fast the running system is. | yes |
| operating-cost | operating cost | cost |  |  | What it costs to run, in compute, storage, licences and people. |  | yes |
| auditability | auditability | governance-and-compliance security |  |  | A third party can reconstruct what happened and why, from the record alone. |  | yes |
| regulatory-compliance | regulatory compliance | governance-and-compliance |  |  | It meets what a law or a regulation requires. |  | yes |
| licence-compliance | licence compliance | governance-and-compliance |  |  | It uses and distributes only as each licence allows. |  | yes |

## Technology

| ID | Label | Broader | Related | Group | Definition | Scope note | Ratified |
|---|---|---|---|---|---|---|---|
| language | language |  |  | yes | A language code or queries are written in. |  | yes |
| standard | standard |  |  | yes | A W3C or other published standard the ontologies or their tools follow. |  | yes |
| platform | platform |  |  | yes | A runtime that code is deployed onto. |  | yes |
| store | store |  |  | yes | A triple store or dataset server. |  | yes |
| library | library |  |  | yes | A library our code calls. |  | yes |
| messaging | messaging |  |  | yes | A protocol or broker messages travel over. |  | yes |
| tool | tool |  |  | yes | A developer tool that is neither a library nor a runtime. |  | yes |
| format | format |  |  | yes | A data or document format. |  | yes |
| notation | notation |  |  | yes | A modelling or diagram notation. |  | yes |
| cloud | cloud |  |  | yes | A hosted cloud provider and its managed services. |  | yes |
| ai | AI |  |  | yes | Machine-learning models and the runtimes, frameworks, protocols and operations around them. |  | yes |
| ai-model | AI model | ai |  | yes | A kind of trained model. |  | yes |
| ai-runtime | AI runtime | ai |  | yes | Software that loads and runs a trained model. |  | yes |
| ai-framework | AI framework | ai |  | yes | A library for building, training or composing models and model calls. |  | yes |
| ai-integration | AI integration | ai |  | yes | How an application or an agent reaches a model and the tools it may use. |  | yes |
| ai-operations | AI operations | ai |  | yes | Evaluating, training, versioning and serving models, the MLOps loop. |  | yes |
| python | Python | language |  |  | Python code, packages and their tests. |  | yes |
| java | Java | language platform |  |  | Java code, Maven modules and their tests. |  | yes |
| sparql | SPARQL | language standard |  |  | SPARQL 1.1 queries and updates. |  | yes |
| typescript | TypeScript | language |  |  | TypeScript, and the JavaScript it compiles to, in applications and add-ins. |  | yes |
| csharp | C# | language |  |  | C# and .NET code. |  | yes |
| erlang | Erlang | language |  |  | Erlang code and the BEAM runtime. |  | yes |
| elixir | Elixir | language |  |  | Elixir code on the BEAM runtime. |  | yes |
| ocaml | OCaml | language |  |  | OCaml code, including code extracted from proofs. |  | yes |
| haskell | Haskell | language |  |  | Haskell code, including code extracted from proofs. |  | yes |
| rust | Rust | language |  |  | Rust code. |  | yes |
| go | Go | language |  |  | Go code. |  | yes |
| sql | SQL | language standard |  |  | SQL queries and schemas. |  | yes |
| shell | shell | language |  |  | POSIX shell, bash and zsh scripts. |  | yes |
| powershell | PowerShell | language |  |  | PowerShell scripts. |  | yes |
| shacl | SHACL | standard |  |  | SHACL shapes, SHACL-SPARQL constraints and validation reports. |  | yes |
| owl | OWL | standard |  |  | OWL axioms, imports, version IRIs and reasoning over them. |  | yes |
| skos | SKOS | standard |  |  | SKOS concept schemes, as the Vocabulary layer governs them. |  | yes |
| bpmn | BPMN | notation standard |  |  | BPMN process models. |  | yes |
| processle | ProcessLE | standard |  |  | ProcessLE process descriptions. |  | yes |
| rdf | RDF | standard |  |  | RDF 1.1 and 1.2, its data model of triples and named graphs. |  | yes |
| rdfs | RDFS | standard |  |  | RDF Schema, with its classes, domains and ranges. |  | yes |
| prov-o | PROV-O | standard |  |  | The PROV ontology for provenance. |  | yes |
| rml | RML | standard |  |  | The RDF Mapping Language, for lifting source data into RDF. |  | yes |
| rdfc | RDFC-1.0 | standard |  |  | RDF Dataset Canonicalization (RDFC-1.0), for hashing graphs. |  | yes |
| scxml | SCXML | standard |  |  | State Chart XML, the W3C statechart notation. |  | yes |
| dmn | DMN | notation standard |  |  | Decision Model and Notation. |  | yes |
| json-schema | JSON Schema | standard |  |  | JSON Schema, for describing and validating JSON. |  | yes |
| openapi | OpenAPI | standard |  |  | OpenAPI descriptions of HTTP interfaces. |  | yes |
| asyncapi | AsyncAPI | standard |  |  | AsyncAPI descriptions of message-driven interfaces. |  | yes |
| ldp | Linked Data Platform | standard |  |  | The W3C Linked Data Platform, and HTTP access to graphs. |  | yes |
| oauth | OAuth and OpenID Connect | standard |  |  | OAuth 2.0 and OpenID Connect. |  | yes |
| tls | TLS | standard |  |  | Transport Layer Security and its certificates. |  | yes |
| cloudevents | CloudEvents | standard |  |  | The CloudEvents envelope for events. |  | yes |
| graphql | GraphQL | messaging standard |  |  | GraphQL schemas and queries. |  | yes |
| grpc | gRPC | messaging standard |  |  | gRPC and Protocol Buffers. |  | yes |
| amqp | AMQP | messaging standard |  |  | The AMQP messaging protocol. |  | yes |
| turtle | Turtle | format |  |  | Turtle, the RDF text format. |  | yes |
| trig | TriG | format |  |  | TriG, Turtle with named graphs. |  | yes |
| n-triples | N-Triples and N-Quads | format |  |  | N-Triples and N-Quads, the line-based RDF formats. |  | yes |
| json-ld | JSON-LD | format standard |  |  | JSON-LD, RDF as JSON. |  | yes |
| xslt | XSLT | language standard |  |  | XSLT and XPath, the W3C languages for transforming XML. |  | no |
| jolt | JOLT | library |  |  | Bazaarvoice JOLT, a JSON to JSON transformation library and its chain specifications. |  | no |
| json | JSON | format |  |  | JSON documents. |  | yes |
| yaml | YAML | format |  |  | YAML documents. |  | yes |
| toml | TOML | format |  |  | TOML configuration files. |  | yes |
| xml | XML | format |  |  | XML documents, including XML catalogs. |  | yes |
| csv | CSV | format |  |  | CSV and other delimited tables. |  | yes |
| markdown | Markdown | format |  |  | Markdown documents, including literate READMEs. |  | yes |
| ooxml | Office Open XML | format |  |  | Office Open XML, the format of Word documents. |  | yes |
| uml | UML | notation |  |  | UML class, state and sequence diagrams. |  | yes |
| archimate | ArchiMate | notation |  |  | ArchiMate, for enterprise architecture views. |  | yes |
| c4 | C4 | notation |  |  | The C4 model of context, container, component and code views. |  | yes |
| er-diagrams | entity-relationship diagrams | notation |  |  | Entity-relationship diagrams. |  | yes |
| mermaid | Mermaid | notation tool |  |  | Mermaid, diagrams written as text. |  | yes |
| fuseki | Fuseki | platform store |  |  | Apache Jena Fuseki as the platform's dataset server. |  | yes |
| jena | Jena | library platform |  |  | The Apache Jena libraries used in Java code, such as its SHACL validator. |  | yes |
| docker | Docker | platform tool |  |  | Docker images and compose stacks. |  | yes |
| node | Node.js | platform |  |  | Node.js, the JavaScript runtime. |  | yes |
| dotnet | .NET | platform |  |  | The .NET runtime. |  | yes |
| browser | browser | platform |  |  | Web browsers, as the runtime of a web application. |  | yes |
| office-add-in | Office add-in | platform |  |  | Microsoft Office add-ins and Office.js. |  | yes |
| kubernetes | Kubernetes | platform |  |  | Kubernetes and its workloads. |  | yes |
| linux | Linux | platform |  |  | Linux hosts. |  | yes |
| macos | macOS | platform |  |  | macOS hosts. |  | yes |
| windows | Windows | platform |  |  | Windows hosts. |  | yes |
| aws | AWS | cloud |  |  | Amazon Web Services. |  | yes |
| azure | Azure | cloud |  |  | Microsoft Azure. |  | yes |
| gcp | Google Cloud | cloud |  |  | Google Cloud. |  | yes |
| oxigraph | Oxigraph | library store |  |  | Oxigraph and pyoxigraph, and how they evaluate SPARQL. |  | yes |
| rdflib | rdflib | library store |  |  | The rdflib Python library and how it evaluates SPARQL. |  | yes |
| postgresql | PostgreSQL | store |  |  | PostgreSQL. |  | yes |
| sqlite | SQLite | store |  |  | SQLite. |  | yes |
| redis | Redis | store |  |  | Redis. |  | yes |
| object-storage | object storage | store |  |  | S3-compatible object storage. |  | yes |
| pyshacl | pySHACL | library |  |  | The pySHACL validator and its cost model. |  | yes |
| owlrl | OWL-RL | library |  |  | The OWL-RL reasoner for rdflib. |  | yes |
| pytest | pytest | library |  |  | pytest and its plugins, such as pytest-xdist. |  | yes |
| junit | JUnit | library |  |  | JUnit. |  | yes |
| react | React | library |  |  | React user interfaces. |  | yes |
| numpy | NumPy | library |  |  | NumPy arrays. |  | yes |
| playwright | Playwright | library tool |  |  | Playwright browser automation and its tests. |  | yes |
| rabbitmq | RabbitMQ | messaging |  |  | RabbitMQ as the platform's message broker. |  | yes |
| mqtt | MQTT | messaging standard |  |  | MQTT messaging. |  | yes |
| http | HTTP | messaging standard |  |  | HTTP services and their semantics, such as ETags and conditional requests. |  | yes |
| websockets | WebSockets | messaging standard |  |  | WebSocket connections. |  | yes |
| kafka | Kafka | messaging store |  |  | Apache Kafka. |  | yes |
| isabelle | Isabelle | tool |  |  | Isabelle theories, sessions and the proof gate. |  | yes |
| git | git | tool |  |  | git, its hooks, and GitHub. |  | yes |
| mise | mise | tool |  |  | mise, its tasks and the toolchains it installs. |  | yes |
| rocq | Rocq | language tool |  |  | The Rocq prover, formerly Coq, and MetaRocq. |  | yes |
| alloy | Alloy | language tool |  |  | The Alloy analyzer and its models. |  | yes |
| maven | Maven | tool |  |  | Maven builds and modules. |  | yes |
| yarn | Yarn and npm | tool |  |  | Yarn and npm, and JavaScript packages. |  | yes |
| pip | pip | tool |  |  | pip, virtual environments and Python packaging. |  | yes |
| github-actions | GitHub Actions | tool |  |  | GitHub Actions workflows. |  | yes |
| terraform | Terraform | tool |  |  | Terraform and OpenTofu. |  | yes |
| helm | Helm | tool |  |  | Helm charts. |  | yes |
| jekyll | Jekyll | tool |  |  | Jekyll, which builds the documentation site. |  | yes |
| opentelemetry | OpenTelemetry | standard tool |  |  | OpenTelemetry traces, metrics and logs. |  | yes |
| prometheus | Prometheus | tool |  |  | Prometheus metrics. |  | yes |
| reuse | REUSE | tool |  |  | The REUSE specification and its lint, for licence headers. |  | yes |
| llm | large language models | ai-model |  |  | Large language models and the interfaces that call them. |  | yes |
| claude | Claude | llm |  |  | Anthropic's Claude models and API. |  | yes |
| gpt | GPT | llm |  |  | OpenAI's GPT models and API. |  | yes |
| gemini | Gemini | llm |  |  | Google's Gemini models and API. |  | yes |
| open-weight-llm | open-weight language models | llm |  |  | Language models whose weights are published, such as Llama, Mistral and Qwen, run on one's own hardware. |  | yes |
| embeddings | embeddings | ai-model |  |  | Embedding models and the vector similarity that ranks by them. |  | yes |
| bge | BGE | embeddings |  |  | The BAAI general embedding models, such as bge-small-en-v1.5. |  | yes |
| static-embeddings | static embeddings | embeddings |  |  | Embeddings looked up per token rather than computed by a transformer, such as model2vec. |  | yes |
| reranker | rerankers | ai-model |  |  | Cross-encoder models that rescore a short list of candidates against a question. |  | yes |
| multimodal-model | multimodal models | ai-model |  |  | Models that read or produce images, audio or video as well as text. |  | yes |
| speech-model | speech models | ai-model |  |  | Speech recognition and speech synthesis models. |  | yes |
| classical-ml | classical machine learning | ai-model |  |  | Linear models, decision trees, gradient boosting, clustering and other machine learning that is not deep learning. |  | yes |
| onnxruntime | ONNX Runtime | ai-runtime library |  |  | ONNX Runtime, for running exported models. |  | yes |
| llama-cpp | llama.cpp | ai-runtime |  |  | llama.cpp and its GGUF models, for running models on a CPU or a laptop. |  | yes |
| vllm | vLLM | ai-runtime |  |  | vLLM and other servers that run models for many callers at once. |  | yes |
| ollama | Ollama | ai-runtime |  |  | Ollama, for running open-weight models locally. |  | yes |
| pytorch | PyTorch | ai-framework library |  |  | PyTorch. |  | yes |
| tensorflow | TensorFlow | ai-framework library |  |  | TensorFlow and Keras. |  | yes |
| jax | JAX | ai-framework library |  |  | JAX. |  | yes |
| transformers | Transformers | ai-framework library |  |  | The Hugging Face Transformers library. |  | yes |
| sentence-transformers | sentence-transformers | ai-framework library |  |  | The sentence-transformers library for embedding and reranking. |  | yes |
| scikit-learn | scikit-learn | ai-framework library |  |  | scikit-learn. |  | yes |
| tokenizers | tokenizers | ai-framework library |  |  | Tokenizer libraries, such as Hugging Face tokenizers and tiktoken. |  | yes |
| langchain | LangChain | ai-framework library |  |  | LangChain and LangGraph, for composing model calls into chains and graphs. |  | yes |
| mcp | Model Context Protocol | ai-integration standard |  |  | The Model Context Protocol, for giving a model tools and data. |  | yes |
| tool-use | tool use | ai-integration |  |  | A model calling functions or tools that an application declares to it. |  | yes |
| agent-sdk | agent SDKs | ai-integration library |  |  | Frameworks for building agents that plan and act with tools, such as the Claude Agent SDK. |  | yes |
| coding-agent | coding agents | ai-integration tool |  |  | Agents that read and change a codebase, such as Claude Code and GitHub Copilot, and the instructions they read. |  | yes |
| structured-output | structured output | ai-integration |  |  | Constraining a model to answer in a schema, such as JSON matching a JSON Schema. |  | yes |
| vector-index | vector indexes | ai store |  |  | Approximate nearest-neighbour indexes, such as HNSW, and the databases built on them. |  | yes |
| model-hub | model hubs | ai-operations |  |  | Registries that publish models and their revisions, such as the Hugging Face Hub. |  | yes |
| model-evaluation | model evaluation | ai-operations |  |  | Benchmarks, question sets and harnesses that measure a model or a system built on one. |  | yes |
| model-training | model training | ai-operations |  |  | Training and fine-tuning models, including adapters such as LoRA. |  | yes |
| experiment-tracking | experiment tracking | ai-operations |  |  | Recording runs, parameters and results, such as with MLflow. |  | yes |
| model-formats | model formats | ai format |  |  | Formats that hold model weights, such as ONNX, GGUF and safetensors. |  | yes |
| gpu | GPUs and accelerators | ai platform |  |  | GPUs and other accelerators, and CUDA. |  | yes |
