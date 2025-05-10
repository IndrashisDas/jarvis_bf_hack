import pandas as pd
import os

# Define the relative path to the CSV file
relative_path = os.path.join(os.path.dirname(__file__), '../../data/master_pv_forecast_input.csv')

# Load the file using the relative path
df = pd.read_csv(relative_path)

# Step 1: Check unique values in 'connection_type' and inspect the data
print("Unique values in 'connection_type':", df['connection_type'].unique())

# Step 2: Check the stats of 'potential_kwp' and 'pv_area_m2'
print("\nPotential KWp stats:\n", df['potential_kwp'].describe())
print("\nPV Area m2 stats:\n", df['pv_area_m2'].describe())

# Step 3: Filter for non-zero 'pv_area_m2' and 'potential_kwp'
df_filtered = df[(df['pv_area_m2'] > 0) & (df['potential_kwp'] > 0)]

# Step 4: Check if there are any rows after this filter
print("\nRows after filtering non-zero 'pv_area_m2' and 'potential_kwp':", df_filtered.shape)

# Step 5: Check unique values in 'connection_type' after filtering
print("\nUnique values in 'connection_type' after filtering:", df_filtered['connection_type'].unique())

# Step 6: Apply connection_type filter if needed (assuming you want to keep 'LV' or 'MV' values)
df_filtered = df_filtered[df_filtered['connection_type'].isin(['LV', 'MV'])]

# Step 7: Check if rows are left after the connection_type filter
print("\nRows after applying 'connection_type' filter:", df_filtered.shape)

# Step 8: Apply 'is_connectable' filter to keep rows where is_connectable is True
df_filtered = df_filtered[df_filtered['is_connectable'] == True]

# Step 9: Check if rows are left after the 'is_connectable' filter
print("\nRows after applying 'is_connectable' filter:", df_filtered.shape)

# Step 10: Check the first 5 rows of the filtered data
print("\nFirst 5 rows of filtered data:\n", df_filtered.head())

# Step 11: Drop columns with all NaN values
df_filtered = df_filtered.dropna(axis=1, how='all')

# Define the relative path to save the filtered file
save_path = os.path.join(os.path.dirname(__file__), '../../data/filtered_master_file.csv')

df_filtered.to_csv(save_path, index=False)
print(f"\nFiltered data saved to '{save_path}'")