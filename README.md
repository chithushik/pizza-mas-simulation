# 🍕 Pizza Multi-Agent Simulation

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.51-red.svg)](https://streamlit.io/)
[![Mesa](https://img.shields.io/badge/Mesa-3.5-orange.svg)](https://mesa.readthedocs.io/)

A complete **multi-agent simulation** of a pizza ordering and delivery system.  
Built with **Python**, **Mesa** (agent-based modeling), **OWLReady2** (ontology), and **Streamlit** (interactive dashboard).

---

## 🚀 New Features (Added by Me)

- ✅ **Shopping Cart** – add multiple pizzas (existing or custom) before checkout  
- ✅ **Custom Pizza Builder** – choose any toppings, name your pizza, and save it to the ontology  
- ✅ **Size & Extra Cheese** – choose Small/Medium/Large and add extra cheese to any order  
- ✅ **One‑Click "Process All Orders"** – runs the simulation until all orders are delivered  
- ✅ **Live Dashboard** – see the message log, status distribution (bar & pie charts), and metrics in real time  

---

## 🧠 Core Features (Original)

- **Ontology‑driven agents** (Customer, Dispatcher, Chef, Courier) using OWL/SWRL
- **Semantic routing** – pizzas are automatically routed to the correct chef (vegetarian vs. non‑vegetarian) based on ontology reasoning
- **Message‑based communication** – orders, bake requests, and delivery messages pass between agents
- **Step‑by‑step simulation** – control the flow manually or run multiple steps at once
- **Fallback routing** – if the reasoner fails, Python logic handles vegetarian classification

---

## 📸 Screenshots

<img width="1847" height="980" alt="pizza1" src="https://github.com/user-attachments/assets/0d6f14ea-eeeb-4e93-90ed-1172ebb7b763" />


<img width="1852" height="837" alt="pizza2" src="https://github.com/user-attachments/assets/81bfba2f-ca48-4d8b-8b8c-239cc899f948" />


<img width="1850" height="832" alt="pizza3" src="https://github.com/user-attachments/assets/c6902bea-981c-4a0a-964a-3ae8899bb01d" />


<img width="1832" height="807" alt="pizza 4" src="https://github.com/user-attachments/assets/80d5d82e-a785-439a-adab-7359e3ae8479" />


---

## 🛠️ Technologies Used

| Technology | Purpose |
|------------|---------|
| **Python 3.12** | Core language |
| **Mesa** | Agent‑Based Modeling framework |
| **OWLReady2** | Ontology management and reasoning |
| **Streamlit** | Interactive web dashboard |
| **Matplotlib** | Chart generation (pie chart) |
| **Pandas** | Data table rendering |
| **SWRL** | Semantic Web Rule Language for routing logic |

---

## 📦 Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/chithushik/pizza-mas-simulation.git
   cd pizza-mas-simulation
