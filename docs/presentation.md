# Master's Thesis Defense & Presentation

## Title of Thesis:
**Collaborative Multi-Agent Simulation Framework for Intelligent Urban Parking Allocation and Traffic Optimization**

- **Candidate:** Deia Melad Mohammed Elghoul
- **Degree:** Master of Software Engineering (Computer Science)
- **Faculty:** Faculty of Information and Communication Technology (FTMK)
- **Institution:** Universiti Teknikal Malaysia Melaka (UTeM)
- **Year:** 2026

---

# Presentation Overview & Slide Navigation

| Slide # | Slide Title | Core Focus |
| :---: | :--- | :--- |
| **1** | Title Slide | Research Title, Candidate, Supervisor, Institution |
| **2** | Presentation Roadmap & Agenda | Flow of the Defense Presentation |
| **3** | Chapter 1: Research Background & Motivation | Urban Parking Cruising Crisis & Systemic Inefficiencies |
| **4** | Chapter 1: Problem Statement & Research Questions | Core Problems and 4 Research Questions (RQ1–RQ4) |
| **5** | Chapter 1: Research Objectives & Scope | 4 Research Objectives (RO1–RO4) and Study Scope |
| **6** | Chapter 2: Literature Review & Identified Research Gaps | Evolution of Smart Parking, Auction Models, & ABMs |
| **7** | Chapter 3: Proposed Multi-Agent System Architecture | 3-Tier MAS Architecture (Driver, Spot, Coordinator) & FIPA-ACL |
| **8** | Chapter 3: Collaborative FPSB Auction & Hungarian Matching | Multi-Attribute Utility Function & $O(n^3)$ Optimization |
| **9** | Chapter 3: Microscopic Traffic Coupling (Mesa 3 + SUMO TraCI) | Hybrid Discrete-Event Physics Integration & OSM City Digital Twins |
| **10** | Chapter 4: Experimental Design & Demand Regimes | 4 Demand Scenarios (Low, Med, High, Peak) & Baseline Models |
| **11** | **TRANSITION: Live Interactive Web Platform Demo** | **Live Demonstration of the Flask Web Dashboard & Real-Time Simulation** |
| **12** | Chapter 4: Live Demo Walkthrough — System Architecture & Run Config | `index.html` & `run.html` (Parameter Sweeps & SUMO Toggle) |
| **13** | Chapter 4: Live Demo Walkthrough — 2D Canvas & OSM GIS Map | `visualize.html` (Canvas Grid, Leaflet Map, Telemetry HUD) |
| **14** | Chapter 4: Live Demo Walkthrough — Results Analytics & History Detail | `results.html` & `history.html` (Run #6 Data & LaTeX Tables) |
| **15** | Chapter 4: Key KPI Results — Parking Search Time (PST) | Proof of 73%–80% Search Time Reduction (Figure 4.1) |
| **16** | Chapter 4: Key KPI Results — Driver Utility & Traffic Flow (TFI) | Multi-Attribute Satisfaction & 80% Congestion Relief (Figs 4.3 & 4.5) |
| **17** | Chapter 4: Summary Statistics & Statistical Significance | Welch's t-tests, Bonferroni Adjustment, Cohen's $d > 1.2$ |
| **18** | Chapter 4: Research Objectives Verification Matrix | Comprehensive Empirical Proof of Objectives 1–4 |
| **19** | Chapter 5: Summary of Research Achievements | Synthesis of Findings & Validation of Core Hypothesis |
| **20** | Chapter 5: Research Contributions (Algorithmic & Engineering) | Theoretical Novelties, Hybrid Architecture, Open Platform |
| **21** | Chapter 5: Practical Implications & Beneficiaries | Benefits for Municipalities, Operators, Commuters, & ITS |
| **22** | Chapter 5: Limitations & Future Research Roadmap | MADRL Bidding, Full-Scale OSM Digital Twins, EV Charging |
| **23** | Concluding Slide & Q&A Session | Final Statement, Acknowledgements, and Floor Open for Questions |

---

# Detailed Slide Content & First-Person Academic Speaking Scripts

---

## SLIDE 1: Title Slide

### Slide Visual Content:
- **Header:** UNIVERSITI TEKNIKAL MALAYSIA MELAKA (UTeM)
- **Title:** Collaborative Multi Agent Simulation Framework for Intelligent Urban Parking Allocation and Traffic Optimization
- **Degree:** Master of Software Engineering (Computer Science)
- **Presenter:** Deia Melad Mohammed Elghoul
- **Faculty:** Faculty of Information and Communication Technology (FTMK)
- **Date:** September 2026

### Presenter's Speaking Script (First-Person Perspective):
> *"Honorable members of the examination committee, esteemed supervisors, and colleagues, good morning. My name is Deia Melad Mohammed Elghoul, and today I am honored to present my Master’s thesis defense entitled **'Collaborative Multi Agent Simulation Framework for Intelligent Urban Parking Allocation and Traffic Optimization'**.*
>
> *In this research, I have addressed one of the most persistent bottlenecks in modern urban mobility—the problem of cruising for parking—by engineering a collaborative, multi-agent allocation system that combines multi-attribute auction theory, microscopic traffic physics, and full-stack interactive telemetry. Allow me to guide you through the motivation, design, empirical proof, and software realization of this research."*

---

## SLIDE 2: Presentation Roadmap & Agenda

### Slide Visual Content:
```
1. Introduction & Research Motivation (Chapter 1)
2. Literature Review & Theoretical Gaps (Chapter 2)
3. Methodology & System Architecture Design (Chapter 3)
4. Experimental Results & Live Site Demonstration (Chapter 4)
   └── [LIVE DEMO: Web Interface, Telemetry HUD, Map Views, Historical Stats]
5. Conclusion, Contributions & Future Recommendations (Chapter 5)
```

### Presenter's Speaking Script:
> *"To provide a clear roadmap for this presentation, I have structured my talk into five core stages:*
> - *First, I will introduce the research background, outlining the severe urban challenges of uncoordinated parking search and stating my four research objectives.*
> - *Second, I will briefly highlight key insights from the literature and identify the exact theoretical and architectural gaps my work bridges.*
> - *Third, I will present my methodology: the three-tier multi-agent architecture, the Hungarian-optimized First-Price Sealed-Bid auction mechanism, and the hybrid Mesa 3 plus SUMO microscopic traffic simulation engine.*
> - *Fourth, I will present the empirical results across four demand regimes, during which I will transition to a live demonstration of our full-stack Flask web platform, showcasing the interactive simulation canvas, OpenStreetMap city digital twins, and statistical analytics.*
> - *Finally, I will conclude with my core scientific contributions, practical implications for smart city stakeholders, study limitations, and future research directions."*

---

## SLIDE 3: Chapter 1 — Research Background & Motivation

### Slide Visual Content:
- **Urbanization Impact:** Massive growth in private vehicular ownership leading to chronic city-center gridlock.
- **The Cruising Dilemma:**
  - Up to **30% of downtown traffic volume** consists solely of drivers searching for vacant parking bays.
  - Drivers spend between **8 to 15 minutes** cruising in Central Business Districts (CBDs).
- **Economic & Environmental Costs:** Hundreds of millions of wasted fuel hours, increased carbon emissions, and heightened driver stress.
- **Flaws of Conventional Smart Parking:**
  - *1st Generation Systems:* Static variable message signs (VMS) or passive occupancy sensors.
  - *Information Without Coordination:* Broadcasting available spots causes drivers to converge on the same facility, shifting rather than solving congestion.

### Presenter's Speaking Script:
> *"Let us examine the problem that motivated my research. In dense metropolitan centers worldwide, up to 30% of traffic congestion is caused by drivers actively cruising for parking. Studies show that motorists waste an average of 10 to 15 minutes searching for parking in high-demand business districts.*
>
> *While the advent of IoT and smart parking sensors provided real-time availability information, these solutions are fundamentally reactive and uncoordinated. When a mobile application simply tells five hundred drivers that fifty spots are vacant in a central parking lot, all five hundred drivers navigate to that same lot, inducing severe localized bottlenecks. In my research, I recognized that urban parking requires a fundamental paradigm shift: moving from passive informational systems to **proactive, collaborative multi-agent coordination**."*

---

## SLIDE 4: Chapter 1 — Problem Statement & Research Questions

### Slide Visual Content:
- **Problem Statement:** Current smart parking systems lack proactive, multi-criteria coordination, failing to capture the complex interdependencies between individual driver preferences and macro-level urban traffic congestion.
- **Research Questions (RQs):**
  - **RQ1:** How to design a multi-agent system to model the dynamic interactions among drivers, parking facilities, and urban traffic infrastructure?
  - **RQ2:** How can parking space utilization be optimized and cruising time minimized using collaborative decision-making algorithms and communication protocols?
  - **RQ3:** How significantly does the proposed framework enhance performance across search time, occupancy balance, and traffic flow under varying demand loads?
  - **RQ4:** How can real-world road networks and real-time visualization be integrated to validate the adaptability of the system?

### Presenter's Speaking Script:
> *"To systematically resolve this challenge, I formulated my problem statement around the lack of multi-agent coordination in existing parking paradigms. This led me to establish four specific research questions:*
> - *RQ1 investigates the architectural design of a decentralized, heterogeneous multi-agent model.*
> - *RQ2 focuses on the mathematical formulation of a collaborative auction mechanism that balances individual driver preferences against social welfare.*
> - *RQ3 examines how the framework behaves quantitatively across varying traffic intensities, from low demand to extreme peak saturation.*
> - *And RQ4 addresses how we can integrate real-world GIS networks and real-time web telemetry to validate practical applicability."*

---

## SLIDE 5: Chapter 1 — Research Objectives & Scope

### Slide Visual Content:
- **Research Objectives (ROs):**
  1. **RO1:** To design and implement a heterogeneous multi-agent architecture with Driver Agents, Parking Spot Agents, and a central Coordinator Agent.
  2. **RO2:** To develop a multi-attribute auction-based allocation mechanism (integrating distance, price, and walking time) coupled with Mesa 3 and SUMO via TraCI.
  3. **RO3:** To quantitatively evaluate system performance using live KPIs: Parking Search Time (PST), Occupancy Variance ($\text{std}(POR)$), Reservation Success Rate (RSR), Driver Utility, and Traffic Flow Impact (TFI).
  4. **RO4:** To benchmark the proposed auction strategy against First-Come-First-Served (FCFS), Greedy, and Random allocation baselines.
- **Research Scope:**
  - Calibrated synthetic urban grid ($100 \times 100$) + OpenStreetMap digital twins for 3 Malaysian cities (Kuala Lumpur, Penang, Johor Bahru).
  - Microscopic physics simulation via SUMO and discrete-event agent logic via Mesa 3.

### Presenter's Speaking Script:
> *"Corresponding to my research questions, I established four primary objectives: first, creating the multi-agent architecture; second, formulating the multi-attribute auction mechanism and coupling it with SUMO traffic physics; third, evaluating system performance across live operational KPIs; and fourth, benchmarking against standard industry baselines.*
>
> *The scope of my research focuses on algorithmic coordination and microscopic traffic simulation, evaluated across both controlled synthetic grids and real OpenStreetMap network digital twins for Kuala Lumpur, George Town, and Johor Bahru."*

---

## SLIDE 6: Chapter 2 — Literature Review & Research Gaps

### Slide Visual Content:
| Area | State of the Art | Identified Gap / Limitation | My Thesis Solution |
| :--- | :--- | :--- | :--- |
| **Smart Parking Systems** | Sensor-based detection & cloud dashboards (Mutambik, 2025) | Information broadcast without coordination; creates secondary congestion | Proactive auction-based pre-allocation before entering congested zones |
| **Multi-Agent Systems** | Contract Net Protocol (CNP), Greedy agents (Icarte-Ahumada, 2025) | High message overhead or selfish routing traps | Single-round First-Price Sealed-Bid (FPSB) auction with Hungarian matching |
| **Simulation Frameworks** | Pure ABMs (NetLogo) or pure traffic simulators (SUMO) | Lack of coupling between agent cognition and microscopic road physics | Hybrid co-simulation: **Mesa 3 + SUMO via TraCI** socket interface |
| **Geospatial Scope** | Abstract mathematical lattices | Limited validation on real urban road topologies | Native ingestion of **OpenStreetMap GIS networks** for 3 metropolitan cities |

### Presenter's Speaking Script:
> *"In my literature review, I surveyed recent advancements across smart parking technologies, multi-agent coordination protocols, and transportation simulators.*
>
> *I identified three critical gaps in the existing body of knowledge:*
> - *First, most multi-agent parking systems rely on iterative Contract Net Protocols or VCG mechanisms, which suffer from severe combinatorial complexity and communication overhead.*
> - *Second, existing studies either model abstract agent decisions without traffic physics, or model traffic physics without intelligent agent reasoning.*
> - *Third, few frameworks validate their algorithms against real-world road networks.*
>
> *My thesis bridges these gaps by combining a single-round FPSB auction with the $O(n^3)$ Hungarian algorithm, coupling Mesa 3 discrete-event logic with SUMO microscopic traffic simulation, and supporting native OpenStreetMap city digital twins."*

---

## SLIDE 7: Chapter 3 — Proposed Multi-Agent System Architecture

### Slide Visual Content:
- **3-Tier Heterogeneous MAS Hierarchy:**
  1. **Driver Agent (Self-Interested Bidder):**
     - Heterogeneous preference vector $(w_d, w_c, w_t) \sim \text{Dirichlet}(1,1,1)$.
     - 4-State Finite State Machine (FSM): `Searching` $\rightarrow$ `Assigned` $\rightarrow$ `Parked` $\rightarrow$ `Departed` (or dropped if $T > T_{max}$).
  2. **Parking Spot Agent (Reactive Resource):**
     - Tracks spatial coordinates $(x,y)$, zone pricing tariff, and occupancy state.
  3. **Coordinator Agent (Central Clearinghouse / Auctioneer):**
     - Aggregates bids, executes the Hungarian matching algorithm, and issues binding assignments.
- **Communication Protocol:** FIPA-ACL messaging semantics (`BID_REQUEST`, `BID_SUBMIT`, `ALLOCATION_RESULT`, `AVAILABILITY_UPDATE`, `DEPARTURE_NOTICE`).

### Presenter's Speaking Script:
> *"Here, I illustrate the multi-agent architecture I designed in Chapter 3. The system consists of three distinct agent layers:*
> - *The **Driver Agent** represents an autonomous motorist with personalized preference weights for distance, parking fees, and walking duration, governed by a four-state Finite State Machine.*
> - *The **Parking Spot Agent** represents a smart parking stall that tracks its occupancy and zone pricing.*
> - *The **Coordinator Agent** acts as an impartial auctioneer, gathering bids each tick and performing global social welfare matching.*
>
> *Communication is strictly asynchronous and adheres to standard FIPA-ACL messaging protocols, ensuring modularity, scalability, and minimal message passing overhead."*

---

## SLIDE 8: Chapter 3 — Collaborative Auction Mechanism & Hungarian Matching

### Slide Visual Content:
- **Multi-Attribute Utility Function:**
  $$U_i(j) = w_d \cdot \hat{d}_{ij} + w_c \cdot \hat{c}_j + w_t \cdot \hat{t}_{ij}$$
  - $\hat{d}_{ij}$: Min-max normalized Euclidean distance from vehicle to spot.
  - $\hat{c}_j$: Min-max normalized hourly tariff of zone $j$.
  - $\hat{t}_{ij}$: Min-max normalized pedestrian walking time from spot $j$ to destination.
  - Constraint: $w_d + w_c + w_t = 1.0$.
- **Winner Determination via Hungarian Algorithm:**
  - Formulated as a maximum-weight bipartite matching on the cost matrix $C = -U$.
  - Solved in deterministic polynomial time $O(n^3)$ where $n$ is the number of active searchers.
  - Guaranteed global social welfare maximization and elimination of duplicate reservation conflicts.

### Presenter's Speaking Script:
> *"To ensure that parking allocations are both fair and systemically optimal, I formulated a multi-attribute utility function that reflects three core driver concerns: distance to the facility, hourly parking cost, and pedestrian walking time to their final destination.*
>
> *Rather than allowing drivers to selfishly grab the nearest spot—which causes severe crowding—the Coordinator Agent constructs a bipartite utility matrix and executes the **Hungarian Algorithm** in $O(n^3)$ time. This guarantees that the sum of utilities across all drivers is globally maximized in every single simulation tick, completely preventing reservation conflicts and tie-breaking ambiguities."*

---

## SLIDE 9: Chapter 3 — Microscopic Traffic Coupling & OSM Digital Twins

### Slide Visual Content:
- **Hybrid Co-Simulation Engine:**
  - **Mesa 3 (Agent Layer):** Discrete-event stepping, bidding rounds, state transitions, and `DataCollector` logging.
  - **SUMO (Physics Layer):** Continuous car-following physics (Krauss model), lane changes, intersection queues, and vehicle velocities.
  - **TraCI Protocol:** Bidirectional socket synchronization translating Mesa allocations into live vehicle target modifications (`traci.vehicle.changeTarget`).
- **3 Malaysian OpenStreetMap Digital Twins:**
  - **Kuala Lumpur CBD:** Bukit Bintang, KLCC, Petronas Towers, Merdeka, Chinatown (570 spots across 5 major zones).
  - **George Town, Penang:** Beach Street, Komtar, Gurney Drive heritage grid.
  - **Johor Bahru City Centre:** JB Sentral, CIQ complex commuter corridors.

### Presenter's Speaking Script:
> *"A key software engineering contribution of my thesis is the seamless integration of Mesa 3 agent logic with SUMO microscopic traffic simulation via the TraCI protocol.*
>
> *Whenever the Mesa coordinator assigns a parking bay, TraCI instantaneously updates the vehicle's route in SUMO, forcing it to follow realistic urban kinematics, obey speed limits, and interact with other vehicles in traffic queues.*
>
> *Furthermore, I built native support for real-world OpenStreetMap digital twins, calibrating road networks and parking zones for three major Malaysian economic hubs: Kuala Lumpur CBD, George Town Penang, and Johor Bahru."*

---

## SLIDE 10: Chapter 4 — Experimental Design & Demand Scenarios

### Slide Visual Content:
- **4 Evaluated Allocation Strategies:**
  1. **Proposed Auction Model** (Hungarian Social Welfare Matching).
  2. **FCFS Model** (First-Come-First-Served chronological queuing).
  3. **Greedy Model** (Uncoordinated nearest-neighbor selection).
  4. **Random Model** (Stochastic unguided selection).
- **4 Demand Regimes (30 Monte Carlo Replications Each, $T=500$ ticks):**
  - **Low Demand ($\lambda = 2$):** $\approx 1,010$ arrivals — Baseline sanity calibration.
  - **Medium Demand ($\lambda = 5$):** $\approx 2,465$ arrivals — Onset of localized competition.
  - **High Demand ($\lambda = 10$):** $\approx 5,955$ arrivals — Saturated CBD conditions.
  - **Peak Demand ($\lambda = 15\text{–}20$):** $\approx 10,072$ arrivals — Extreme scarcity stress testing.

### Presenter's Speaking Script:
> *"Moving into Chapter 4, I conducted an exhaustive empirical evaluation comparing my proposed Auction mechanism against FCFS, Greedy, and Random baselines across four sequential demand scenarios, executing 30 independent Monte Carlo replications per configuration with a discarded 50-tick warm-up phase.*
>
> *At this stage, I would like to transition to a live demonstration of our deployed web application to show how these experiments run in real time."*

---

## SLIDE 11: TRANSITION — Live Interactive Web Platform Demo

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║                     >>> LIVE DEMONSTRATION TRANSITION <<<                    ║
║                                                                              ║
║           Demonstrating the Multi-Agent Urban Parking Web Platform           ║
║                     Deployed at: http://localhost:5000                       ║
║                                                                              ║
║   Key Views to Demonstrate:                                                  ║
║   1. Home Dashboard (`index.html`)                                           ║
║   2. Simulation Configurator & Runner (`run.html`)                           ║
║   3. Live 2D Grid Canvas & OSM Leaflet Map (`visualize.html`)                ║
║   4. Real-Time Telemetry HUD & Playback Controls                             ║
║   5. Post-Run Analytics & Performance Deltas (`results.html`)                ║
║   6. Historical SQLite Archive & Raw Run Data (`history.html`)               ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

### Presenter's Speaking Script:
> *"I will now share my screen to demonstrate the live Flask web platform that I developed to operate, monitor, and visualize this multi-agent simulation framework in real time."*

---

## SLIDE 12: Live Demo Walkthrough — System Architecture & Run Config

### Slide Visual Content:
- **Home Dashboard (`index.html`):**
  - Displays system status, active background workers, quick experiment presets, and architectural summaries.
- **Simulation Configurator & Launcher (`run.html`):**
  - Dynamic parameter inputs: Grid Size ($100 \times 100$), Spots ($200$), Arrival Rate $\lambda$ ($2\text{--}20$), Dwell Distribution $(\mu_d=50, \sigma_d=15)$, Timeout $T_{max}=30$.
  - Strategy dropdown: `Auction`, `FCFS`, `Random`, `Greedy`.
  - City selector: `Synthetic Grid`, `Kuala Lumpur CBD`, `Penang`, `Johor Bahru`.
  - Toggle for SUMO microscopic physics and graphical TraCI window.

### Presenter's Speaking Script (During Live Demo):
> *"As you can see on screen, this is the Home Dashboard of our platform (`index.html`), providing an overview of system health and active experiments.*
>
> *When we navigate to the **Simulation Runner** page (`run.html`), we have full interactive control over the simulation parameters. We can configure the grid dimensions, number of parking bays, driver arrival rates, and dwell time distributions. We can select our proposed Auction model or any baseline, choose between the synthetic grid or real Malaysian cities like Kuala Lumpur, and toggle SUMO TraCI integration. When I click 'Launch Simulation', an asynchronous job is dispatched to a background worker thread."*

---

## SLIDE 13: Live Demo Walkthrough — 2D Canvas & OSM GIS Map

### Slide Visual Content:
- **Interactive Simulation View (`visualize.html`):**
  - **Dual Mode Visualizer:**
    1. *Synthetic 2D Canvas:* Displays the road network graph, 8 colored parking zones, vacant spots (green), occupied spots (red), and moving driver agent vectors.
    2. *Real-World Leaflet Map:* Overlays real OpenStreetMap tiles for Kuala Lumpur CBD, rendering exact parking lot geofences and live vehicle GPS positions.
  - **Real-Time Telemetry HUD:**
    - Live Simulation Tick & Clock.
    - Active Cruising vs. Parked Vehicles.
    - Instantaneous Parking Occupancy Rate (POR %).
    - Rolling Average Parking Search Time (PST).
    - Current Driver Mean Utility Gauge.
  - **Playback Engine:** Play, Pause, Step-by-Step, Reset, and Speed multiplier slider ($1\times\text{--}10\times$).

### Presenter's Speaking Script (During Live Demo):
> *"Here on the **Live Visualization** page (`visualize.html`), we see the core of our multi-agent framework in action. In synthetic mode, the canvas renders each vehicle navigating the road network toward assigned zones. When we switch to the Kuala Lumpur city scenario, the system loads real OpenStreetMap tiles through Leaflet, plotting real parking facilities like KLCC and Bukit Bintang.*
>
> *Notice the live Telemetry HUD on the upper right: it continuously monitors active cruising vehicles, instantaneous occupancy rate, and rolling search time. With the playback controls, we can pause the execution, step through individual auction rounds, or accelerate the simulation up to ten times speed."*

---

## SLIDE 14: Live Demo Walkthrough — Results Analytics & History Detail

### Slide Visual Content:
- **Analytics View (`results.html`):**
  - Multi-metric bar charts, boxplots of search time distributions, and occupancy timeseries graphs generated via Plotly/Chart.js.
  - Delta percentage cards showing performance improvements.
- **History Detail View (`history.html` — e.g., `/history/run/6`):**
  - Direct connection to SQLite database (`output/experiments.sqlite`).
  - Raw replication logs, metric comparisons across all 4 demand scenarios and all 4 models.
  - One-click export of consolidated CSV datasets and publication-ready LaTeX tables (`results_table.tex`).

### Presenter's Speaking Script (During Live Demo):
> *"Finally, once a simulation batch concludes, the platform redirects to the **Results Analytics** page (`results.html`), displaying comparative boxplots and timeseries curves.*
>
> *In the **History Archive** (`history.html`), as seen in Run #6, all raw replication records and summary statistics are permanently stored in our SQLite database. From here, researchers can inspect individual vehicle completion counts, analyze raw logs, or export automated LaTeX tables directly into their thesis manuscripts.*
>
> *I will now switch back to the slides to examine the formal statistical results."*

---

## SLIDE 15: Chapter 4 — Key KPI Results: Parking Search Time (PST)

### Slide Visual Content:
```
Mean Parking Search Time (PST in simulation ticks):
┌────────────────────┬──────────┬──────────┬──────────┬──────────┐
│ Scenario           │ Auction  │ FCFS     │ Random   │ Greedy   │
├────────────────────┼──────────┼──────────┼──────────┼──────────┤
│ Low Demand (λ=2)   │ 1.00     │ 1.00     │ 1.00     │ 1.00     │
│ Medium Demand (λ=5)│ 4.81 *** │ 23.82    │ 23.82    │ 23.82    │
│ High Demand (λ=10) │ 6.60 *** │ 27.02    │ 27.02    │ 27.02    │
│ Peak Demand (λ=20) │ 7.36 *** │ 27.15    │ 27.15    │ 27.15    │
└────────────────────┴──────────┴──────────┴──────────┴──────────┘
*** Statistically significant reduction (p < 0.001, Cohen's d = -40.12)
```
- **Key Finding:** Proposed Auction model achieves a **73% to 80% reduction** in cruising delays across all congested demand regimes.

### Presenter's Speaking Script:
> *"Examining our primary operational metric—Parking Search Time (PST)—the empirical evidence is decisive. In Low Demand, with abundant parking, all models converge at 1.0 tick.*
>
> *However, as soon as we enter Medium Demand ($\lambda=5$), uncoordinated baselines collapse into extensive cruising loops, averaging 23.82 ticks. My proposed Auction mechanism resolves allocations in just **4.81 ticks**—a **79.8% reduction in search time**.*
>
> *Under High and Peak demand, while baseline search times degrade to over 27 ticks (approaching the $T_{max}=30$ timeout), the Auction coordinator maintains rapid, bounded matching within **6.60 to 7.36 ticks**, representing an improvement of over 72%."*

---

## SLIDE 16: Chapter 4 — Key KPI Results: Driver Utility & Traffic Flow (TFI)

### Slide Visual Content:
- **Driver Mean Utility ($U \in [0, 1]$):**
  - **Auction:** $0.794\text{--}0.891$ across all demand levels.
  - **FCFS / Random:** $0.623\text{--}0.643$ (stagnant).
  - **Greedy:** $0.681\text{--}0.784$ (sub-optimal).
  - *Outcome:* Auction yields **25% to 40% higher driver satisfaction** by simultaneously optimizing distance, price, and walking time.
- **Traffic Flow Impact (TFI — Road Network Congestion Index):**
  - **Medium Demand:** Auction $\text{TFI} = 3.768$ vs. Baseline $\text{TFI} = 18.887$ (**80.0% reduction** in road congestion).
  - **High / Peak Demand:** Auction $\text{TFI} = 1.458\text{--}2.177$ vs. Baseline $\text{TFI} = 5.537\text{--}9.129$ (**74% reduction**).

### Presenter's Speaking Script:
> *"Turning to Driver Utility and Traffic Flow Impact:*
> - *First, in terms of driver satisfaction, my proposed Auction model consistently achieves utility scores between **0.794 and 0.891**, compared to 0.62 for FCFS and 0.68 for Greedy. Because the Hungarian algorithm optimizes global social welfare across distance, price, and walking time, drivers receive spots that match their specific preference profiles.*
> - *Second, looking at the macroscopic traffic impact, the TFI index proves that directing vehicles straight to reserved spots slashes cruising-induced road congestion by **up to 80%** in medium demand, preventing the formation of gridlock around popular destinations."*

---

## SLIDE 17: Chapter 4 — Summary Statistics & Statistical Significance

### Slide Visual Content:
- **Formal Statistical Significance Testing (Table 4.4 in Thesis):**
  - Two-sample **Welch's t-test** (robust to unequal variances).
  - **Bonferroni correction** applied for multiple comparisons ($\alpha = 0.05 / 3 = 0.0167$).
  - All comparisons for PST, Utility, and TFI yielded $p$-values $< 10^{-12}$ ($p < 0.001$).
  - **Effect Size (Cohen's $d$):**
    - Search Time: $d = -40.12$ (Extremely large effect size).
    - Driver Utility: $d = +4.25$ to $+7.98$.
    - Traffic Flow Impact: $d = -31.05$ to $-47.19$.
- **Conclusion:** Performance gains are statistically robust and reproducible.

### Presenter's Speaking Script:
> *"To verify that these results were not random artifacts of Monte Carlo stochasticity, I conducted formal statistical hypothesis testing using Welch's t-tests and Bonferroni corrections across all 30 replications.*
>
> *As shown in Table 4.4 of the thesis, all improvements achieved by the Auction model are statistically significant at $p < 0.001$. Furthermore, the effect sizes calculated via Cohen’s $d$ exceed $|d| > 4.0$, and in the case of search time reach $d = -40.12$, confirming that the observed improvements possess immense practical and operational significance."*

---

## SLIDE 18: Chapter 4 — Research Objectives Verification Matrix

### Slide Visual Content:
| Research Objective | Methodology Design | Empirical Evidence (Chapter 4) | Final Status |
| :--- | :--- | :--- | :---: |
| **RO1: MAS Architecture** | 3-tier FSM hierarchy with FIPA-ACL | Verified across 30 replications and live web canvas telemetry | **Fully Achieved** |
| **RO2: Auction Mechanism** | Multi-attribute FPSB + Hungarian $O(n^3)$ | Social welfare maximized; $0.79\text{--}0.89$ utility; SUMO TraCI coupling | **Fully Achieved** |
| **RO3: Live KPI Assessment** | Measure PST, $\text{std}(POR)$, RSR, Utility, TFI | Systematically evaluated across 4 demand regimes in SQLite database | **Fully Achieved** |
| **RO4: Baseline Benchmarking** | Compare with FCFS, Greedy, Random | Statistically proven: 73%–80% lower PST, 80% lower TFI ($p<0.001$) | **Fully Achieved** |

### Presenter's Speaking Script:
> *"This brings us to the formal verification of my research objectives. As summarized in this matrix, all four objectives set out in Chapter 1 have been completely fulfilled and empirically proven in Chapter 4:*
> - *RO1 is verified through stable multi-agent telemetry.*
> - *RO2 is proven through Hungarian social welfare optimization.*
> - *RO3 is validated through comprehensive KPI tracking.*
> - *And RO4 is confirmed through rigorous statistical benchmarking against all baseline models."*

---

## SLIDE 19: Chapter 5 — Summary of Research Achievements

### Slide Visual Content:
- **Core Hypothesis Validated:** Proactive, collaborative multi-agent coordination decisively outperforms reactive and uncoordinated smart parking mechanisms.
- **Key Empirical Takeaways:**
  1. *Cruising Elimination:* Eliminates unguided cruising, reducing search delays by up to 80%.
  2. *Preference Satisfaction:* Balances diverse driver trade-offs (proximity vs. cost vs. walking distance).
  3. *Macroscopic Traffic Relief:* Mitigates urban road friction by 75%–80%.
  4. *Computational Tractability:* Hungarian matching executes in $<12\text{ms}$ per cycle, proving real-time viability.

### Presenter's Speaking Script:
> *"In Chapter 5, I synthesize the core conclusions of this research. My study provides definitive proof for our central hypothesis: collaborative multi-agent coordination solves the urban parking cruising dilemma.*
>
> *By replacing selfish nearest-neighbor routing with centralized Hungarian matching, the framework eliminates blind searching, satisfies heterogeneous driver preferences, reduces urban road congestion, and executes in under 12 milliseconds per allocation cycle."*

---

## SLIDE 20: Chapter 5 — Research Contributions

### Slide Visual Content:
1. **Algorithmic & Theoretical Contributions:**
   - Closed-loop multi-attribute utility formulation with Dirichlet preference heterogeneity.
   - Bipartite Hungarian matching applied to social welfare maximization in dynamic ABMs.
2. **Software Engineering & Architectural Contributions:**
   - Hybrid co-simulation architecture coupling **Mesa 3** discrete-event reasoning with **SUMO** microscopic physics via TraCI.
   - Standardized FIPA-ACL asynchronous messaging protocols minimizing broadcast overhead.
3. **Full-Stack Observability Platform Contributions:**
   - Real-time Flask web application with 2D Canvas rendering, Leaflet OpenStreetMap digital twins (KL, Penang, JB), and automated SQLite/LaTeX reporting.

### Presenter's Speaking Script:
> *"My thesis delivers three major contributions:*
> - *Theoretically, it formulates a closed-loop multi-attribute matching model that balances individual driver trade-offs against city-wide social welfare.*
> - *Architecturally, it establishes a robust, reproducible co-simulation pipeline integrating Mesa 3 with SUMO traffic physics.*
> - *And from a software engineering perspective, it delivers a full-stack open platform featuring real-time HUD telemetry, OpenStreetMap digital twins, and automated data archival."*

---

## SLIDE 21: Chapter 5 — Practical Implications & Beneficiaries

### Slide Visual Content:
- **Municipal Transport Authorities & Planners:**
  - Direct reduction of CBD congestion (up to 30% traffic volume reduction).
  - Virtual sandbox to test new parking facility layouts and dynamic pricing policies before capital expenditure.
- **Commercial Parking Facility Operators:**
  - Minimizes spatial occupancy variance ($\text{std}(POR)$), distributing demand evenly and preventing underutilization of peripheral bays.
- **Commuters & Motorists:**
  - Transforms stressful, unpredictable cruising into direct-to-spot navigation with guaranteed reservations.
- **Smart City & ITS Developers:**
  - Extensible, microservice-ready codebase for smart curb management and autonomous fleet dispatching.

### Presenter's Speaking Script:
> *"The practical implications of this research extend across multiple urban stakeholders:*
> - *Municipal transport authorities gain a powerful tool to reduce downtown traffic emissions and simulate infrastructure investments.*
> - *Commercial parking operators can balance occupancy across facilities to stabilize revenues.*
> - *Daily commuters benefit from guaranteed reservations and massive time savings.*
> - *And ITS software engineers receive a validated, modular multi-agent software architecture for next-generation mobility services."*

---

## SLIDE 22: Chapter 5 — Limitations & Future Research Roadmap

### Slide Visual Content:
- **Study Limitations:**
  - Calibrated grid testing vs. irregular dynamic traffic signal networks.
  - 100% compliance assumption (absence of spot poaching or illegal parking).
  - Static base pricing per zone without real-time surge pricing.
  - Idealized lossless communication bus.
- **Future Research Directions:**
  1. **Multi-Agent Deep Reinforcement Learning (MADRL):** Empowering agents with MAPPO/MADDPG for adaptive bidding and dynamic pricing.
  2. **Full-Scale OSM Field Validation:** Large-scale deployment across complex metropolitan networks with SCATS/SCOOT adaptive traffic lights.
  3. **Electric Vehicle (EV) Smart Charging Co-Allocation:** Integrating battery State-of-Charge (SoC) and charger scheduling.
  4. **V2X & Edge Cloud Deployment:** Transitioning coordinator logic to 5G/C-V2X edge brokers.
  5. **Mixed-Autonomy Studies:** Evaluating sensitivity across 20% to 100% MAS penetration rates.

### Presenter's Speaking Script:
> *"To ensure academic rigor, I have documented the limitations of my study, including the assumption of full driver compliance and static baseline zone tariffs.*
>
> *These limitations establish an exciting roadmap for future work, including applying Multi-Agent Deep Reinforcement Learning for dynamic surge pricing, co-allocating Electric Vehicle charging stalls with battery state-of-charge constraints, and evaluating partial penetration rates in mixed-autonomy connected vehicle fleets."*

---

## SLIDE 23: Concluding Slide & Q&A Session

### Slide Visual Content:
```
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║                                  THANK YOU                                   ║
║                                                                              ║
║        Collaborative Multi-Agent Simulation Framework for Intelligent        ║
║               Urban Parking Allocation and Traffic Optimization              ║
║                                                                              ║
║                          Deia Melad Mohammed Elghoul                         ║
║            Master of Software Engineering (Computer Science), 2026           ║
║               Faculty of Information and Communication Technology            ║
║                    Universiti Teknikal Malaysia Melaka (UTeM)                ║
║                                                                              ║
║                      >>> FLOOR OPEN FOR QUESTIONS <<<                        ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
```

### Presenter's Speaking Script:
> *"In conclusion, this research demonstrates that collaborative, auction-based multi-agent coordination provides an efficient, scalable, and equitable solution to urban parking congestion in modern smart cities.*
>
> *I would like to express my sincere gratitude to my supervisor, the faculty of FTMK, and the examination committee for your invaluable guidance and time.*
>
> *Thank you very much. I am now delighted to open the floor and welcome your questions and feedback."*
