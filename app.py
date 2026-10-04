import streamlit as st
import json
import time
import urllib.parse
from google import genai
from google.genai import types

st.set_page_config(
    page_title="Receipt Splitter",
    page_icon="🧾",
    layout="centered"
)

st.title("🧾 Receipt Splitter")
st.write("Upload a receipt and split the bill with your friends.")

client = genai.Client(
    api_key=st.secrets["GEMINI_API_KEY"]
)

uploaded_file = st.file_uploader(
    "Upload your receipt",
    type=["jpg", "jpeg", "png"]
)

if uploaded_file:

    st.image(
        uploaded_file,
        caption="Uploaded Receipt",
        width="stretch"
    )

    if st.button("🔍 Analyze Receipt", width="stretch"):

        with st.spinner("AI is reading your receipt..."):

            image_part = types.Part.from_bytes(
                data=uploaded_file.getvalue(),
                mime_type=uploaded_file.type
            )

            prompt = """
Analyze this receipt image carefully.

Return ONLY valid JSON using exactly this structure:

{
    "store": "store name",
    "date": "date",
    "items": [
        {
            "name": "item name",
            "quantity": 1,
            "price": 100.00
        }
    ],
    "subtotal": 0.00,
    "tax": 0.00,
    "discount": 0.00,
    "total": 0.00
}

Rules:
1. Include every visible item.
2. Include quantity.
3. Price is the total price for that line item.
4. Do not invent information.
5. If a value is not visible, use 0.
6. Return ONLY JSON.
"""

            response = None
            success = False
            last_error = None

            for attempt in range(4):

                try:

                    response = client.models.generate_content(
                        model="gemini-3.8-flash",
                        contents=[
                            prompt,
                            image_part
                        ]
                    )

                    success = True
                    break

                except Exception as e:

                    last_error = e
                    error_text = str(e)

                    if (
                        "503" in error_text
                        or "UNAVAILABLE" in error_text
                    ):

                        if attempt < 3:

                            wait_time = 2 ** (attempt + 1)
                            time.sleep(wait_time)

                        else:
                            break

                    else:
                        break

            if success:

                try:

                    cleaned_response = response.text.strip()

                    if cleaned_response.startswith("```json"):
                        cleaned_response = cleaned_response[7:]

                    elif cleaned_response.startswith("```"):
                        cleaned_response = cleaned_response[3:]

                    if cleaned_response.endswith("```"):
                        cleaned_response = cleaned_response[:-3]

                    cleaned_response = cleaned_response.strip()

                    receipt_data = json.loads(
                        cleaned_response
                    )

                    st.session_state["receipt_data"] = receipt_data

                    if "shares" in st.session_state:
                        del st.session_state["shares"]

                    if "whatsapp_message" in st.session_state:
                        del st.session_state["whatsapp_message"]

                    st.success(
                        "Receipt analyzed successfully!"
                    )

                except json.JSONDecodeError:

                    st.error(
                        "AI returned an invalid format."
                    )

                    st.code(response.text)

            else:

                error_text = str(last_error)

                if (
                    "503" in error_text
                    or "UNAVAILABLE" in error_text
                ):

                    st.error(
                        "Gemini is temporarily busy. "
                        "Please wait a few seconds and try again."
                    )

                else:

                    st.error(
                        "Something went wrong while analyzing the receipt."
                    )

                    st.write(error_text)


if "receipt_data" in st.session_state:

    receipt = st.session_state["receipt_data"]

    st.divider()

    st.subheader("🏪 Receipt Information")

    st.write(
        f"**Store:** {receipt.get('store', 'Not available')}"
    )

    st.write(
        f"**Date:** {receipt.get('date', 'Not available')}"
    )

    st.subheader("🛒 Items")

    items = receipt.get("items", [])

    for item in items:

        name = item.get("name", "Unknown")
        quantity = item.get("quantity", 1)
        price = float(item.get("price", 0))

        st.write(
            f"**{name}** × {quantity} — ₹{price:.2f}"
        )

    st.divider()

    st.subheader("💰 Bill Summary")

    subtotal = float(receipt.get("subtotal", 0))
    tax = float(receipt.get("tax", 0))
    discount = float(receipt.get("discount", 0))
    total = float(receipt.get("total", 0))

    st.write(f"Subtotal: ₹{subtotal:.2f}")
    st.write(f"Tax: ₹{tax:.2f}")
    st.write(f"Discount: ₹{discount:.2f}")

    st.markdown(f"### Total: ₹{total:.2f}")

    st.divider()

    st.subheader("👥 Split the Bill")

    number_of_people = st.number_input(
        "How many people are splitting the bill?",
        min_value=1,
        max_value=10,
        value=2,
        step=1
    )

    st.write("Enter the names of the people:")

    people = []

    for i in range(int(number_of_people)):

        name = st.text_input(
            f"Person {i + 1}",
            value=f"Person {i + 1}",
            key=f"person_{i}"
        )

        people.append(name.strip())

    st.divider()

    st.subheader("🍕 Who had what?")

    st.caption(
        "For each item, select everyone who shared it."
    )

    assignments = {}

    for index, item in enumerate(items):

        item_name = item.get("name", "Unknown")
        item_price = float(item.get("price", 0))
        item_quantity = item.get("quantity", 1)

        st.markdown(f"#### 🍽️ {item_name}")

        st.write(
            f"Quantity: {item_quantity} | Price: ₹{item_price:.2f}"
        )

        selected_people = []

        for person_index, person in enumerate(people):

            selected = st.checkbox(
                person,
                value=True,
                key=f"item_{index}_person_{person_index}"
            )

            if selected:
                selected_people.append(person)

        assignments[index] = {
            "name": item_name,
            "price": item_price,
            "people": selected_people
        }

        st.divider()

    if st.button(
        "💰 Calculate Split",
        width="stretch"
    ):

        if any(not person for person in people):

            st.error(
                "Please enter a name for every person."
            )

        elif len(set(people)) != len(people):

            st.error(
                "Please use different names for each person."
            )

        elif any(
            not data["people"]
            for data in assignments.values()
        ):

            st.error(
                "Please select at least one person for every item."
            )

        else:

            shares = {}

            for person in people:
                shares[person] = 0.0

            for data in assignments.values():

                price = data["price"]
                selected_people = data["people"]

                share_per_person = (
                    price / len(selected_people)
                )

                for person in selected_people:

                    shares[person] += share_per_person

            item_subtotal = sum(
                data["price"]
                for data in assignments.values()
            )

            if item_subtotal > 0:

                for person in people:

                    person_item_share = shares[person]

                    tax_share = (
                        person_item_share
                        / item_subtotal
                    ) * tax

                    discount_share = (
                        person_item_share
                        / item_subtotal
                    ) * discount

                    shares[person] += tax_share
                    shares[person] -= discount_share

            st.session_state["shares"] = shares

            if "whatsapp_message" in st.session_state:
                del st.session_state["whatsapp_message"]


if "shares" in st.session_state:

    shares = st.session_state["shares"]

    st.divider()

    st.subheader("💳 Final Split")

    for person, amount in shares.items():

        st.write(
            f"**{person}** → ₹{amount:.2f}"
        )

    st.divider()

    total_calculated = sum(shares.values())

    st.write(
        f"**Calculated Total:** ₹{total_calculated:.2f}"
    )

    st.write(
        f"**Receipt Total:** ₹{total:.2f}"
    )

    difference = total_calculated - total

    if abs(difference) < 0.01:

        st.success(
            "✅ Split matches the receipt total."
        )

        st.divider()

        st.subheader("📱 WhatsApp Message")

        if st.button(
            "🤖 Generate WhatsApp Message",
            width="stretch"
        ):

            with st.spinner(
                "AI is creating the WhatsApp message..."
            ):

                split_text = ""

                for person, amount in shares.items():

                    split_text += (
                        f"{person}: ₹{amount:.2f}\n"
                    )

                whatsapp_prompt = f"""
Create a short, friendly WhatsApp message
for a group of friends after splitting a bill.

Receipt store:
{receipt.get("store", "Unknown")}

Receipt total:
₹{total:.2f}

Individual shares:
{split_text}

The message should:
- Be natural and easy to read.
- Mention the store.
- Mention each person's amount.
- Mention the total.
- Use a few suitable emojis.
- Do not add fake information.
- Do not use markdown tables.
- Return ONLY the final WhatsApp message.
"""

                message_response = None
                message_success = False
                message_error = None

                for attempt in range(4):

                    try:

                        message_response = (
                            client.models.generate_content(
                                model="gemini-3.8-flash",
                                contents=[
                                    whatsapp_prompt
                                ]
                            )
                        )

                        message_success = True
                        break

                    except Exception as e:

                        message_error = e
                        error_text = str(e)

                        if (
                            "503" in error_text
                            or "UNAVAILABLE" in error_text
                        ):

                            if attempt < 3:

                                wait_time = 2 ** (attempt + 1)

                                time.sleep(
                                    wait_time
                                )

                            else:
                                break

                        else:
                            break

                if message_success:

                    whatsapp_message = (
                        message_response.text.strip()
                    )

                    if whatsapp_message.startswith("```"):

                        whatsapp_message = (
                            whatsapp_message
                            .replace("```", "")
                            .strip()
                        )

                    st.session_state[
                        "whatsapp_message"
                    ] = whatsapp_message

                else:

                    if (
                        "503" in str(message_error)
                        or "UNAVAILABLE" in str(message_error)
                    ):

                        st.error(
                            "Gemini is temporarily busy. "
                            "Please try generating the message again."
                        )

                    else:

                        st.error(
                            "Could not generate the WhatsApp message."
                        )

                        st.write(
                            str(message_error)
                        )

    if "whatsapp_message" in st.session_state:

        whatsapp_message = st.session_state[
            "whatsapp_message"
        ]

        st.text_area(
            "Generated message",
            value=whatsapp_message,
            height=180
        )

        encoded_message = urllib.parse.quote(
            whatsapp_message
        )

        whatsapp_url = (
            "https://wa.me/?text="
            + encoded_message
        )

        st.markdown(
            f"""
            <a href="{whatsapp_url}"
               target="_blank"
               style="
               display:block;
               text-align:center;
               padding:12px;
               background:#25D366;
               color:white;
               text-decoration:none;
               border-radius:8px;
               font-weight:bold;
               ">
               📲 Send on WhatsApp
            </a>
            """,
            unsafe_allow_html=True
        )

    else:

        if abs(difference) >= 0.01:

            st.warning(
                f"⚠️ Difference: ₹{difference:.2f}"
            )
