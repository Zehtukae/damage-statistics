import re
from collections import defaultdict
import numpy as np
import streamlit as st
import plotly.express as px
import pandas as pd
import datetime

class DamageInfo:
    def __init__(self):
        self.total_damage_inflicted = 0
        self.damage_inflicted_by_type = defaultdict(int)
        self.total_damage_received = 0
        self.damage_received_by_type = defaultdict(int)

    def add_damage_inflicted(self, damage, damage_type):
        self.total_damage_inflicted += damage
        self.damage_inflicted_by_type[damage_type] += damage

    def add_damage_received(self, damage, damage_type):
        self.total_damage_received += damage
        self.damage_received_by_type[damage_type] += damage

    @property
    def total_damage(self):
        return self.total_damage_inflicted + self.total_damage_received

def process_damage_data(files):
    """Process damage data from uploaded log files."""
    damage_info = defaultdict(DamageInfo)
    pattern = re.compile(r"Defender: ([\w\s']+), Attacker: ([\w\s']+), Type: (\w*), Damage: (\d+), Cause: (\w+)")

    for file in files:
        file_contents = file.read().decode("utf-8")
        for line in file_contents.split("\n"):
            match = pattern.search(line)
            if match:
                defender, attacker, damage_type, damage, _ = match.groups()
                attacker, defender = attacker.strip(), defender.strip()
                damage_info[attacker].add_damage_inflicted(int(damage), damage_type)
                damage_info[defender].add_damage_received(int(damage), damage_type)

    return damage_info

def format_damage_output(damage_data, use_allowlist=False, allowlist=None):
    """Format damage data into a markdown string."""
    total_inflicted_damage_all = sum(data.total_damage_inflicted for data in damage_data.values())

    if use_allowlist and allowlist:
        filtered_damage_data = {char: data for char, data in damage_data.items() if char in allowlist}
        total_inflicted_damage_allowlist = sum(data.total_damage_inflicted for data in filtered_damage_data.values())
    else:
        filtered_damage_data = damage_data
        total_inflicted_damage_allowlist = total_inflicted_damage_all

    num_characters = len(allowlist) if use_allowlist and allowlist else len(damage_data)
    target_percentage_per_character = 100 / num_characters if num_characters > 0 else 0

    output = f"### Damage Statistics: Target: {target_percentage_per_character:.2f}%\n\n"
    output += f"**Total Damage Inflicted by All:** {total_inflicted_damage_all}\n\n"

    if use_allowlist:
        total_inflicted_damage_non_party = total_inflicted_damage_all - total_inflicted_damage_allowlist
        percent_damage_allowlist = (total_inflicted_damage_allowlist / total_inflicted_damage_all * 100) if total_inflicted_damage_all > 0 else 0
        percent_damage_non_party = (total_inflicted_damage_non_party / total_inflicted_damage_all * 100) if total_inflicted_damage_all > 0 else 0
        output += f"**Total Damage Inflicted by Allowlist (Party):** {total_inflicted_damage_allowlist} ({percent_damage_allowlist:.2f}%)\n\n"
        output += f"**Total Damage Inflicted by Non-Party:** {total_inflicted_damage_non_party} ({percent_damage_non_party:.2f}%)\n\n\n"

    sorted_characters = sorted(filtered_damage_data.items(), key=lambda x: x[1].total_damage_inflicted, reverse=True)

    for character, data in sorted_characters:
        if use_allowlist:
            percent_of_total = (data.total_damage_inflicted / total_inflicted_damage_allowlist) * 100 if total_inflicted_damage_allowlist > 0 else 0
            offset_from_target = percent_of_total - target_percentage_per_character
        else:
            percent_of_total = (data.total_damage_inflicted / total_inflicted_damage_all) * 100 if total_inflicted_damage_all > 0 else 0
            offset_from_target = percent_of_total - target_percentage_per_character

        output += f"**{character}** - Total Inflicted: {data.total_damage_inflicted} ({percent_of_total:.2f}%, Offset: {offset_from_target:+.2f}%)\n"
        inflicted_str = ', '.join(f"{t or 'Unknown'}: {d}" for t, d in sorted(data.damage_inflicted_by_type.items(), key=lambda x: x[1], reverse=True) if d > 0)
        output += f"- **Damage Inflicted:** {inflicted_str}\n"
        received_str = ', '.join(f"{t or 'Unknown'}: {d}" for t, d in sorted(data.damage_received_by_type.items(), key=lambda x: x[1], reverse=True) if d > 0)
        output += f"- **Damage Received:** {received_str}\n\n"

    # Calculate performance statistics and classify character performance
    total_damages = [data.total_damage for data in filtered_damage_data.values()]
    inflicted_damages = [data.total_damage_inflicted for data in filtered_damage_data.values()]
    received_damages = [data.total_damage_received for data in filtered_damage_data.values()]

    q1_total, median_total, q3_total = np.percentile(total_damages, [25, 50, 75])

    q1_inflicted, _, q3_inflicted = np.percentile(inflicted_damages, [25, 50, 75])
    iqr_inflicted = q3_inflicted - q1_inflicted
    upper_fence_inflicted = q3_inflicted + (1.5 * iqr_inflicted)
    lower_fence_inflicted = q1_inflicted - (1.5 * iqr_inflicted)

    q1_received, _, q3_received = np.percentile(received_damages, [25, 50, 75])
    iqr_received = q3_received - q1_received
    upper_fence_received = q3_received + (1.5 * iqr_received)
    lower_fence_received = q1_received - (1.5 * iqr_received)

    def classify_performance(damage, q1, q3, upper_fence, lower_fence):
        if damage > upper_fence:
            return "Outlier"
        elif damage > q3:
            return "Excellent"
        elif damage >= q1:
            return "Good"
        elif damage < lower_fence:
            return "Outlier"
        else:
            return "Low"

    output += "\n### Performance Categories\n"
    for character, data in filtered_damage_data.items():
        inflicted_performance = classify_performance(data.total_damage_inflicted, q1_inflicted, q3_inflicted, upper_fence_inflicted, lower_fence_inflicted)
        received_performance = classify_performance(data.total_damage_received, q1_received, q3_received, upper_fence_received, lower_fence_received)

        if data.total_damage < q1_total:
            output += f"- **{character} (Low)** - Damage Dealt: {inflicted_performance}, Damage Taken: {received_performance}\n"
        elif data.total_damage > q3_total:
            output += f"- **{character} (Excellent)** - Damage Dealt: {inflicted_performance}, Damage Taken: {received_performance}\n"
        else:
            output += f"- **{character} (Good)** - Damage Dealt: {inflicted_performance}, Damage Taken: {received_performance}\n"

    return output

def create_dashboard(damage_data, allowlist=None):
    """Create a dashboard with graphs using Streamlit and Plotly."""
    filtered_damage_data = {char: data for char, data in damage_data.items() if char in allowlist} if allowlist else damage_data

    # Create a DataFrame for the damage data
    data = []
    for character, info in filtered_damage_data.items():
        for damage_type, damage in info.damage_inflicted_by_type.items():
            data.append({'Character': character, 'Damage Type': damage_type, 'Damage Inflicted': damage})
        for damage_type, damage in info.damage_received_by_type.items():
            data.append({'Character': character, 'Damage Type': damage_type, 'Damage Received': damage})

    df = pd.DataFrame(data)

    st.markdown("### Graphs")

    # Create stacked bar chart for damage inflicted by type for each character
    fig_inflicted_by_type = px.bar(df[df['Damage Inflicted'].notna()], x='Character', y='Damage Inflicted', color='Damage Type', title='Damage Inflicted by Type')
    st.plotly_chart(fig_inflicted_by_type)

    # Create stacked bar chart for damage received by type for each character
    fig_received_by_type = px.bar(df[df['Damage Received'].notna()], x='Character', y='Damage Received', color='Damage Type', title='Damage Received by Type')
    st.plotly_chart(fig_received_by_type)

def main():
    """Main function to run the Streamlit app."""
    st.title("Damage Analysis Dashboard")

    uploaded_files = st.file_uploader("Upload log files", accept_multiple_files=True)
    player_names = st.text_input("Enter player names (comma-separated)")
    use_allowlist = st.checkbox("Use player names allowlist", value=True)

    if uploaded_files:
        # Check for duplicate file names
        file_names = [file.name for file in uploaded_files]
        if len(file_names) != len(set(file_names)):
            st.warning("Warning: Duplicate log files detected.")

        damage_data = process_damage_data(uploaded_files)
        allowlist = [name.strip() for name in player_names.split(",")] if player_names else None

        # Check for names that do not exist in the allowlist
        if use_allowlist and allowlist:
            missing_names = [name for name in allowlist if name not in damage_data]
            if missing_names:
                st.warning(f"Warning: The following names do not exist in the data: {', '.join(missing_names)}")
                allowlist = [name for name in allowlist if name in damage_data]

        # Display the formatted damage output
        output = format_damage_output(damage_data, use_allowlist=use_allowlist, allowlist=allowlist)
        st.markdown(output)

        # Create the dashboard with graphs
        create_dashboard(damage_data, allowlist if use_allowlist else None)

        # Get current time
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Print debug message to the console
        debug_message = f"Debug: Damage report generated at {current_time}\n"
        if use_allowlist and allowlist:
            player_damages = []
            total_damage = 0
            for player in allowlist:
                player_damage = damage_data[player].total_damage_inflicted if player in damage_data else 0
                player_damages.append(f"{player}: {player_damage}")
                total_damage += player_damage
            debug_message += f"Players in session: {', '.join(player_damages)} | Total: {total_damage}"
        else:
            total_damage = sum(data.total_damage_inflicted for data in damage_data.values())
            debug_message += f"Total damage: {total_damage}"

        print(debug_message)
        
if __name__ == "__main__":
    main()
