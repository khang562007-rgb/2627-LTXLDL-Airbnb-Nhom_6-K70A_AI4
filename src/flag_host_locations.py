import pandas as pd
import numpy as np

def process_host_location_flags(df: pd.DataFrame, area_bounds: dict = None) -> pd.DataFrame:
    df = df.copy()

    df['dup_id_in_snapshot'] = df['id'].duplicated(keep=False)

    df['host_id_missing'] = df['host_id'].isna()

    declared_counts = pd.to_numeric(df['host_listings_count'], errors='coerce')
    sample_counts = df['host_id'].map(df['host_id'].value_counts())
    df['host_count_inconsistent'] = sample_counts > declared_counts

    host_since_dt = pd.to_datetime(df['host_since'], errors='coerce')
    last_scraped_dt = pd.to_datetime(df['last_scraped'], errors='coerce')
    df['host_since_invalid'] = host_since_dt.isna() | (host_since_dt > last_scraped_dt)

    rate_clean = df['host_response_rate'].astype(str).str.replace('%', '', regex=False).str.strip()
    df['host_response_rate_clean'] = pd.to_numeric(rate_clean, errors='coerce') / 100.0
    df['host_rate_type'] = df['host_response_rate'].notna() & df['host_response_rate_clean'].isna()

    for col in ['host_is_superhost', 'instant_bookable', 'host_has_profile_pic', 'host_identity_verified']:
        df[f'{col}_clean'] = df[col].astype(str).str.lower().map({'t': True, 'f': False})

    lat = pd.to_numeric(df['latitude'], errors='coerce')
    lon = pd.to_numeric(df['longitude'], errors='coerce')

    valid_lat = lat.between(-90, 90, inclusive='both')
    valid_lon = lon.between(-180, 180, inclusive='both')
    df['coord_missing_or_invalid'] = ~(valid_lat & valid_lon) | lat.isna() | lon.isna()

    df['coord_outside_porto'] = ~(lat.between(41.10, 41.25) & lon.between(-8.70, -8.50))

    if area_bounds in df.columns:
        def check_outside(row_idx):
            area = df.loc[row_idx, 'analysis_area']
            r_lat, r_lon = lat.loc[row_idx], lon.loc[row_idx]
            if area in area_bounds and pd.notna(r_lat) and pd.notna(r_lon):
                min_lat, max_lat, min_lon, max_lon = area_bounds[area]
                return not (min_lat <= r_lat <= max_lat and min_lon <= r_lon <= max_lon)
            return True
        df['coord_outside_area'] = [check_outside(i) for i in df.index]
    else:
        df['coord_outside_area'] = False

    df['neighbourhood_missing_or_unknown'] = df['neighbourhood_cleansed'].isna()

    return df