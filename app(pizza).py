import streamlit as st
import random
import matplotlib.pyplot as plt
from collections import Counter
import pandas as pd

# ---------- Simulation code (unchanged) ----------
from mesa import Agent, Model
from owlready2 import (
    World, Thing, ObjectProperty, DataProperty, Not,
    Imp, sync_reasoner_pellet
)

# ---- Ontology setup ----
world = World()
onto = world.get_ontology("http://example.org/pizza.owl")

with onto:
    class Pizza(Thing): ...
    class Topping(Thing): ...
    class MeatTopping(Topping): ...
    class VegTopping(Topping): ...

    class hasTopping(ObjectProperty):
        domain = [Pizza]
        range = [Topping]

    class VegetarianPizza(Pizza):
        equivalent_to = [Pizza & Not(hasTopping.some(MeatTopping))]
        pass

    class AgentThing(Thing): ...
    class Chef(AgentThing): ...
    class Customer(AgentThing): ...
    class Courier(AgentThing): ...
    class Dispatcher(AgentThing): ...

    class Task(Thing): ...
    class OrderPizzaTask(Task): ...
    class BakePizzaTask(Task): ...
    class DeliverPizzaTask(Task): ...
    class DispatchTask(Task): ...

    class hasTask(ObjectProperty):
        domain = [AgentThing]
        range = [Task]

    class vegetarianOnly(DataProperty):
        domain = [Chef]
        range = [bool]

    class Message(Thing): ...
    class OrderRequest(Message): ...
    class BakeOrder(Message): ...
    class DeliveryOrder(Message): ...

    class sender(ObjectProperty):
        domain = [Message]
        range = [AgentThing]
    class receiver(ObjectProperty):
        domain = [Message]
        range = [AgentThing]
    class aboutPizza(ObjectProperty):
        domain = [Message]
        range = [Pizza]
    class quantity(DataProperty):
        domain = [Message]
        range = [int]

onto.save(file="pizza_ontology.owl", format="rdfxml")

# ---- Predefined toppings and pizzas ----
with onto:
    tomato = onto.VegTopping("TomatoSauce")
    mozzarella = onto.VegTopping("Mozzarella")
    basil = onto.VegTopping("Basil")
    pepperoni = onto.MeatTopping("Pepperoni")
    chicken = onto.MeatTopping("Chicken")
    ham = onto.MeatTopping("Ham")
    pineapple = onto.VegTopping("Pineapple")

    margherita = onto.Pizza("MargheritaPizza")
    margherita.hasTopping = [tomato, mozzarella, basil]

    pepperoni_pizza = onto.Pizza("PepperoniPizza")
    pepperoni_pizza.hasTopping = [tomato, mozzarella, pepperoni]

    bbq_chicken = onto.Pizza("BBQChickenPizza")
    bbq_chicken.hasTopping = [tomato, mozzarella, chicken]

    hawaiian = onto.Pizza("HawaiianPizza")
    hawaiian.hasTopping = [tomato, mozzarella, ham, pineapple]

# ---- Agent individuals ----
with onto:
    cust1_ind = onto.Customer("cust1")
    cust1_ind.hasTask = [onto.OrderPizzaTask()]

    chefVeg_ind = onto.Chef("chefVeg")
    chefVeg_ind.hasTask = [onto.BakePizzaTask()]
    chefVeg_ind.vegetarianOnly = [True]

    chefAll_ind = onto.Chef("chefAll")
    chefAll_ind.hasTask = [onto.BakePizzaTask()]
    chefAll_ind.vegetarianOnly = [False]

    courier1_ind = onto.Courier("courier1")
    courier1_ind.hasTask = [onto.DeliverPizzaTask()]

    dispatcher_ind = onto.Dispatcher("dispatcher1")
    dispatcher_ind.hasTask = [onto.DispatchTask()]

# SWRL Rules
with onto:
    rule_route_veg = Imp()
    rule_route_veg.set_as_rule(f"""
        OrderRequest(?m) ^ aboutPizza(?m, ?p) ^ VegetarianPizza(?p) -> receiver(?m, {chefVeg_ind.name})
    """)

with onto:
    rule_nonveg = Imp()
    rule_nonveg.set_as_rule(f"""
        OrderRequest(?m) ^ aboutPizza(?m, ?p) ^ hasTopping(?p, ?t) ^ MeatTopping(?t)
        -> receiver(?m, {chefAll_ind.name})
    """)

# Reasoner helpers
def try_reason(label:str=""):
    try:
        sync_reasoner_pellet(infer_property_values=True, debug=0)
        return True
    except Exception:
        return False

def is_vegetarian(pizza_ind) -> bool:
    try:
        return onto.VegetarianPizza in pizza_ind.is_a
    except Exception:
        return all(not isinstance(t, onto.MeatTopping) for t in pizza_ind.hasTopping)

# ---- BusMessage ----
class BusMessage:
    def __init__(self, owl_ind, mtype: str, sender_id: str, receiver_id: str, pizza_ind, qty: int,
                 size: str = "Medium", extra_cheese: bool = False):
        self.owl_ind = owl_ind
        self.type = mtype
        self.sender_id = sender_id
        self.receiver_id = receiver_id
        self.pizza = pizza_ind
        self.qty = qty
        self.size = size
        self.extra_cheese = extra_cheese
        self.processed = False
        self.status = "CREATED"
        self.step_created = 0

    def set_status(self, new_status):
        self.status = new_status

    def __repr__(self):
        cheese = "+cheese" if self.extra_cheese else ""
        return f"<Msg {self.type} {self.pizza.name} ({self.size}{cheese}) x{self.qty} {self.sender_id}->{self.receiver_id} status={self.status}>"

# ---- MAS Model & Agents ----
class PizzaMAS(Model):
    def __init__(self):
        super().__init__()
        self.messages = []
        self.baked = 0
        self.delivered = 0
        self.reasoner_available = False
        self.cust = cust1_ind
        self.chefVeg = chefVeg_ind
        self.chefAll = chefAll_ind
        self.courier = courier1_ind
        self.dispatcher = dispatcher_ind

        self.agent_customer = CustomerAgent("cust1", self, self.cust)
        self.agent_dispatcher = DispatcherAgent("dispatcher1", self, self.dispatcher)
        self.agent_chefVeg = ChefAgent("chefVeg", self, self.chefVeg)
        self.agent_chefAll = ChefAgent("chefAll", self, self.chefAll)
        self.agent_courier = CourierAgent("courier1", self, self.courier)
        self.agent_manager = ManagerAgent("manager1", self, None)

        self._customer_has_ordered = False
        self.reasoner_available = try_reason("initial")

    def send_order(self, sender_name, pizza_ind, qty=1, size="Medium", extra_cheese=False):
        with onto:
            try:
                sender_ind = getattr(onto, sender_name)
            except AttributeError:
                sender_ind = onto.Customer(sender_name)
                sender_ind.hasTask = [onto.OrderPizzaTask()]
            owl_msg = onto.OrderRequest(f"order_{sender_name}_{random.randrange(1_000_000)}")
            owl_msg.sender = [sender_ind]
            owl_msg.aboutPizza = [pizza_ind]
            owl_msg.quantity = [qty]
        msg = BusMessage(owl_msg, "order", sender_name, None, pizza_ind, qty, size, extra_cheese)
        msg.status = "ORDERED"
        msg.step_created = len(self.messages)
        self.messages.append(msg)

    def send_bake(self, sender_name, receiver_name, pizza_ind, qty, size="Medium", extra_cheese=False):
        with onto:
            owl_msg = onto.BakeOrder(f"bake_{sender_name}_{random.randrange(1_000_000)}")
            owl_msg.sender = [getattr(onto, sender_name)]
            owl_msg.receiver = [getattr(onto, receiver_name)]
            owl_msg.aboutPizza = [pizza_ind]
            owl_msg.quantity = [qty]
        msg = BusMessage(owl_msg, "bake", sender_name, receiver_name, pizza_ind, qty, size, extra_cheese)
        self.messages.append(msg)

    def send_delivery(self, sender_name, receiver_name, pizza_ind, qty, size="Medium", extra_cheese=False):
        with onto:
            owl_msg = onto.DeliveryOrder(f"deliv_{sender_name}_{random.randrange(1_000_000)}")
            owl_msg.sender = [getattr(onto, sender_name)]
            owl_msg.receiver = [getattr(onto, receiver_name)]
            owl_msg.aboutPizza = [pizza_ind]
            owl_msg.quantity = [qty]
        msg = BusMessage(owl_msg, "deliver", sender_name, receiver_name, pizza_ind, qty, size, extra_cheese)
        self.messages.append(msg)

    def step(self):
        # Disable automatic customer ordering
        # self.agent_customer.step()
        self.reasoner_available = try_reason("per-step")
        self.agent_dispatcher.step()
        self.agent_chefVeg.step()
        self.agent_chefAll.step()
        self.agent_courier.step()
        self.agent_manager.step()

    def is_all_delivered(self):
        if not self.messages:
            return False
        return all(msg.status == "DELIVERED" for msg in self.messages)

class OntologyBackedAgent(Agent):
    def __init__(self, unique_id, model, owl_ind):
        super().__init__(model)
        self.name = unique_id
        self.owl_ind = owl_ind

class CustomerAgent(OntologyBackedAgent):
    def step(self):
        if self.model._customer_has_ordered:
            return
        pizzas = list(onto.Pizza.instances())
        veg = [p for p in pizzas if is_vegetarian(p)]
        pizza = random.choice(veg if veg else pizzas)
        qty = random.choice([1, 2])
        self.model.send_order(self.name, pizza, qty)
        self.model._customer_has_ordered = True

class DispatcherAgent(OntologyBackedAgent):
    def step(self):
        for msg in self.model.messages:
            if msg.type != "order" or msg.processed:
                continue
            owlr = getattr(msg.owl_ind, "receiver", [])
            if owlr:
                recv_name = owlr[0].name
                self.model.send_bake(self.name, recv_name, msg.pizza, msg.qty, msg.size, msg.extra_cheese)
                msg.set_status("ROUTED")
                msg.processed = True
                continue
            recv_name = "chefVeg" if is_vegetarian(msg.pizza) else "chefAll"
            self.model.send_bake(self.name, recv_name, msg.pizza, msg.qty, msg.size, msg.extra_cheese)
            msg.set_status("ROUTED")
            msg.processed = True

class ChefAgent(OntologyBackedAgent):
    def step(self):
        for msg in self.model.messages:
            if msg.type != "bake" or msg.processed:
                continue
            if msg.receiver_id != self.name:
                continue
            veg_only_vals = getattr(self.owl_ind, "vegetarianOnly", [])
            veg_only = bool(veg_only_vals and veg_only_vals[0])
            if veg_only and not is_vegetarian(msg.pizza):
                msg.processed = True
                continue
            msg.set_status("BAKING")
            self.model.baked += msg.qty
            msg.set_status("BAKED")
            self.model.send_delivery(self.name, "courier1", msg.pizza, msg.qty, msg.size, msg.extra_cheese)
            msg.processed = True

class CourierAgent(OntologyBackedAgent):
    def step(self):
        for msg in self.model.messages:
            if msg.type != "deliver" or msg.processed:
                continue
            if msg.receiver_id != self.name:
                continue
            self.model.delivered += msg.qty
            msg.set_status("DELIVERED")
            msg.processed = True

class ManagerAgent(OntologyBackedAgent):
    def step(self):
        pass

# ---------- Streamlit App with Cart ----------
st.set_page_config(page_title="🍕 Pizza MAS", layout="wide")
st.title("🍕 Pizza Multi-Agent Simulation")

# ---- Session state ----
if 'model' not in st.session_state:
    st.session_state.model = PizzaMAS()
    st.session_state.step_count = 0

if 'cart' not in st.session_state:
    st.session_state.cart = []  # list of dicts

# ---- Sidebar: Pizza Builder ----
st.sidebar.header("🛒 Order Pizza")
pizza_choice = st.sidebar.radio("Pizza selection", ["Existing pizza", "Create custom"], index=0)

if pizza_choice == "Existing pizza":
    pizza_names = [p.name for p in onto.Pizza.instances()]
    selected_pizza = st.sidebar.selectbox("Choose a pizza", pizza_names)
    pizza_ind = None
    for p in onto.Pizza.instances():
        if p.name == selected_pizza:
            pizza_ind = p
            break
    if pizza_ind:
        toppings_display = ", ".join([t.name for t in pizza_ind.hasTopping])
        st.sidebar.caption(f"Toppings: {toppings_display}")
else:
    st.sidebar.subheader("Create your own pizza")
    all_toppings = list(onto.Topping.instances())
    topping_names = [t.name for t in all_toppings]
    selected_toppings = st.sidebar.multiselect("Select toppings", topping_names)
    custom_pizza_name = st.sidebar.text_input("Pizza name", value="MyPizza")

size = st.sidebar.radio("Size", ["Small", "Medium", "Large"], index=1)
extra_cheese = st.sidebar.checkbox("Extra Cheese")
qty = st.sidebar.number_input("Quantity", min_value=1, max_value=5, value=1, step=1)

# Add to Cart
if st.sidebar.button("➕ Add to Cart"):
    if pizza_choice == "Existing pizza":
        if pizza_ind is None:
            st.sidebar.error("Select a pizza")
        else:
            item = {
                "pizza_name": pizza_ind.name,
                "pizza_ind": pizza_ind,
                "toppings": [t.name for t in pizza_ind.hasTopping],
                "qty": qty,
                "size": size,
                "extra_cheese": extra_cheese
            }
            st.session_state.cart.append(item)
            st.sidebar.success(f"Added {pizza_ind.name} ({size}) x{qty}")
            st.rerun()
    else:
        if not selected_toppings:
            st.sidebar.error("Select at least one topping.")
        elif not custom_pizza_name.strip():
            st.sidebar.error("Enter a name.")
        else:
            # Ensure pizza exists in ontology
            with onto:
                existing = None
                for p in onto.Pizza.instances():
                    if p.name == custom_pizza_name:
                        existing = p
                        break
                if existing:
                    pizza_ind = existing
                    existing.hasTopping = []  # overwrite toppings
                else:
                    pizza_ind = onto.Pizza(custom_pizza_name)
                for t_name in selected_toppings:
                    for t in all_toppings:
                        if t.name == t_name:
                            pizza_ind.hasTopping.append(t)
                            break
            item = {
                "pizza_name": pizza_ind.name,
                "pizza_ind": pizza_ind,
                "toppings": selected_toppings,
                "qty": qty,
                "size": size,
                "extra_cheese": extra_cheese
            }
            st.session_state.cart.append(item)
            st.sidebar.success(f"Added custom pizza '{custom_pizza_name}' ({size}) x{qty}")
            st.rerun()

# ---- Cart actions in sidebar ----
st.sidebar.markdown("---")
st.sidebar.subheader("🛒 Cart")

if st.sidebar.button("🗑️ Clear Cart"):
    st.session_state.cart = []
    st.rerun()

if st.sidebar.button("✅ Checkout"):
    if not st.session_state.cart:
        st.sidebar.error("Cart is empty.")
    else:
        for item in st.session_state.cart:
            pizza_ind = item["pizza_ind"]
            qty_item = item["qty"]
            size_item = item["size"]
            cheese_item = item["extra_cheese"]
            st.session_state.model.send_order("user", pizza_ind, qty_item, size_item, cheese_item)
        st.session_state.cart = []
        st.sidebar.success(f"✅ {len(st.session_state.cart)} orders placed! Use 'Process All Orders' to deliver.")
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.header("Controls")
step_button = st.sidebar.button("➡️ Next Step", use_container_width=True)
reset_button = st.sidebar.button("🔄 Reset", use_container_width=True)

# NEW: Process All Orders button
process_all_button = st.sidebar.button("🚀 Process All Orders", use_container_width=True)

num_steps = st.sidebar.slider("Steps to run", 1, 10, 1)
auto_button = st.sidebar.button(f"▶️ Run {num_steps} Steps", use_container_width=True)

# ---- Main area ----
col1, col2, col3 = st.columns(3)
col1.metric("Steps", st.session_state.step_count)
col2.metric("Baked", st.session_state.model.baked)
col3.metric("Delivered", st.session_state.model.delivered)

# ---- Cart display ----
if st.session_state.cart:
    st.subheader("🛒 Your Cart")
    cart_data = []
    for idx, item in enumerate(st.session_state.cart):
        cart_data.append({
            "Pizza": item["pizza_name"],
            "Toppings": ", ".join(item["toppings"]),
            "Size": item["size"],
            "Extra Cheese": "✅" if item["extra_cheese"] else "❌",
            "Qty": item["qty"]
        })
    df_cart = pd.DataFrame(cart_data)
    st.dataframe(df_cart, use_container_width=True)

    cols = st.columns(len(st.session_state.cart))
    for i, (col, item) in enumerate(zip(cols, st.session_state.cart)):
        if col.button(f"Remove {item['pizza_name']}", key=f"remove_{i}"):
            st.session_state.cart.pop(i)
            st.rerun()
else:
    st.info("Your cart is empty. Add some pizzas!")

# ---- Simulation messages and charts ----
if st.session_state.model.messages:
    data = []
    for msg in st.session_state.model.messages:
        data.append({
            "Type": msg.type,
            "Pizza": msg.pizza.name,
            "Size": msg.size,
            "Extra Cheese": "✅" if msg.extra_cheese else "❌",
            "Qty": msg.qty,
            "Sender": msg.sender_id,
            "Receiver": msg.receiver_id or "?",
            "Status": msg.status
        })
    df = pd.DataFrame(data)
    st.subheader("📋 Message Log")
    st.dataframe(df, use_container_width=True)

    # Status distribution chart
    status_counts = Counter(msg.status for msg in st.session_state.model.messages)
    st.subheader("📊 Status Distribution")
    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        st.bar_chart(status_counts)
    with col_chart2:
        fig, ax = plt.subplots()
        colors = ["#FFA500", "#1E90FF", "#FFD700", "#32CD32", "#00CED1", "#D3D3D3"]
        ax.pie(status_counts.values(), labels=status_counts.keys(), autopct='%1.1f%%', colors=colors[:len(status_counts)])
        ax.axis('equal')
        st.pyplot(fig)
else:
    st.info("No messages yet. Add items to cart and checkout.")

# ---- Handle actions ----
if reset_button:
    st.session_state.model = PizzaMAS()
    st.session_state.step_count = 0
    st.session_state.cart = []
    st.rerun()

if step_button:
    st.session_state.model.step()
    st.session_state.step_count += 1
    st.rerun()

if auto_button:
    for _ in range(num_steps):
        st.session_state.model.step()
        st.session_state.step_count += 1
    st.rerun()

if process_all_button:
    # Step until all messages are delivered (or max 20 steps to avoid infinite loops)
    for _ in range(20):
        if st.session_state.model.is_all_delivered():
            break
        st.session_state.model.step()
        st.session_state.step_count += 1
    if st.session_state.model.is_all_delivered():
        st.sidebar.success("✅ All orders delivered!")
    else:
        st.sidebar.warning("Not all orders delivered after 20 steps. Click Next Step to continue.")
    st.rerun()