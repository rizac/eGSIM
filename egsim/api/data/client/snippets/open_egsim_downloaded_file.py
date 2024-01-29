import os
import pandas as pd  # https://pandas.pydata.org/docs/user_guide/dsintro.html#dataframe
import tables  # required to save/read pd.DataFrame in HDF format (see format in the function below)


def open_egsim_downloaded_file(file_path: str) -> pd.DataFrame:
    """Open a tabular data file downloaded from eGSIM in HDF or CSV format

    Args:
        file_path: A string denoting the path to a valid file, in CSV or HDF format,
            downloaded from the eGSIM platform or API . The format will be inferred
            from the file extension ('.csv', '.hdf', '.h5', '.hdf5', '.he5'),
            ignoring the case
    Returns:
        a pandas DataFrame
    """
    file_ext = os.path.splitext(file_path)[1].lower()
    csv_ext = ('.csv',)  # 1-element tuple
    hdf_ext = ('.hdf', '.h5', '.hdf5', '.he5')
    if file_ext in csv_ext:
        return pd.read_csv(file_path, header=[0, 1, 2], index_col=0)
    elif file_ext in hdf_ext:
        return pd.read_hdf(file_path)
    else:
        raise ValueError(f'Unrecognized file extension "{file_ext}" '
                         f'not in {csv_ext + hdf_ext}')
