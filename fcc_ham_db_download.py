
# This script downloads the full FCC ham radio database 
# and creates a local SQLite copy along with some
# additional tables which make the data a bit more 
# user friendly to browse. 

import requests
import zipfile
import os
import shutil
from pathlib import Path
import pandas as pd
import sqlite3
import platform


def clean_temp_files(destination: str | os.PathLike, dest_unpacked: str | os.PathLike) -> None:
    '''Do a little housekeeping to remove old versions of these files'''
    if os.path.isdir(dest_unpacked):
        shutil.rmtree(dest_unpacked)
    if os.path.isfile(destination):
        os.remove(destination)

def get_database(url: str, destination: str | os.PathLike) -> None:
    '''Sends web request to get the raw .zip file from the FCC'''
    print(f'Starting file download from: {url}')
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        with open(destination, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
            print(f'Compressed FCC database files downloaded to "{destination}"')
    except requests.exceptions.RequestException as e:
        print(f'Error downloading file: {e}')
    print()

def unpack_data_files(destination: str | os.PathLike, dest_unpacked: str | os.PathLike) -> None:
    '''Unpacks the .zip file so we can access the files'''
    try:
        with zipfile.ZipFile(destination,'r') as zip_ref:
            os.makedirs(dest_unpacked, exist_ok=True)
            zip_ref.extractall(dest_unpacked)
        print(f'{destination} extracted to "{dest_unpacked}"')
        # fix a linux-specific bug in the filenames
        if platform.system() == 'Linux':
            for f in Path(dest_unpacked).glob('*.dat'):
                f.rename(f.with_suffix('.DAT'))
    except zipfile.BadZipFile:
        print(f'Error: {destination} is not a valid zip file')
    except FileNotFoundError:
        print(f'Error: Zip file not found at {destination}')
    except Exception as e:
        print(f'Error extracting Zip file {e}')
    print()

def make_table(dest_unpacked: str | os.PathLike, headers: list, source_name: str) -> pd.DataFrame:
    '''Creates a table from the .DAT files apply appropriate column names'''
    df = pd.read_table(dest_unpacked.joinpath(source_name),
                       delimiter='|',
                       index_col=False,
                       header=None,
                       names = [i[1] for i in headers],
                       usecols=[i[0]-1 for i in headers],
                       dtype='str')
    # take care of any leading or trailing whitespace
    for col in df.columns:
        df[col] = df[col].str.strip()
    return df

def data_qc(database_dir: str | os.PathLike, new_tables: dict) -> list:
    '''Checks size of new tables and only specifies those with additional records for updating'''
    with sqlite3.connect(database_dir) as conn:
        # extract current record counts and immediately make a dictionary of them
        try:
            current_counts = pd.read_sql('select * from row_counts',conn).to_dict(orient='records')[0]
        except (pd.io.sql.DatabaseError, sqlite3.OperationalError):
            # most likely exception is a database error if row_counts doesn't exist
            # make an empty dict and make sure all tables are created
            current_counts = {}


    tables_to_update = []
    tables_to_keep = []

    for table_name, table in new_tables.items():
        if len(current_counts) == 0:
            tables_to_update.append(table_name)
        else:
            existing_count = current_counts[table_name]
            new_count = len(table)
            if new_count >= existing_count:
                print(f'Table - "{table_name}" had {existing_count:,} records and the new update has {new_count:,} records.')
                tables_to_update.append(table_name)
            else:
                print(f'Table - "{table_name}" had {existing_count:,} records and the new update has {new_count:,} records.')
                print(f'\tThis table will not be updated.')
                tables_to_keep.append(table_name)
        
    if len(tables_to_update) > 0:
        print(f'The following tables will be re-built with new data: {', '.join(tables_to_update)}')
    if len(tables_to_keep) > 0:
        print(f'The following tables will not be updated: {', '.join(tables_to_keep)}')
    print()
    return tables_to_update

    


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    '''
    Does some light cleaning of the data. Casts
    names and cities to title case, states to 
    upper case, and dates to datetimes, coercing
    any bad dates to NaT
    '''

        
    for col in df.columns:
        if col in ['first_name','last_name','city']:
            df[col] = df[col].str.title()
        if col == 'state':
            df[col] = df[col].str.upper()
        if col.endswith('_date'):
            df[col] = pd.to_datetime(df[col],format='%m/%d/%Y',errors='coerce')

    return df

def make_create_scripts(schema: dict) -> list:
    '''Using the database schema, generates create scripts for the tables'''
    create_scripts = []
    for table_name, schema_list in schema.items():
        script = f''' 
        CREATE TABLE IF NOT EXISTS {table_name}(
        '''

        columns = ',\n'.join([f'{col} {dtype}' for _,col,dtype in schema_list])
        script += columns + ')'
        create_scripts.append(script)

    return create_scripts

def define_schema() -> dict:
    '''Defines column positions, column names, and datatypes for each 
        field in the tables. This schema is then used in populating the database
    '''
    schema = {}

    AM_schema = [
    [1,'record_type','TEXT'],
    [2,'uid','INTEGER'],
    [3,'uls_file_number','TEXT'],
    [4,'ebf_number','TEXT'],
    [5,'callsign','TEXT'],
    [6,'operator_class','TEXT'],
    [7,'group_code','TEXT'],
    [8,'region_code','TEXT'],
    [9,'trustee_callsign','TEXT'],
    [10,'trustee_indicator','TEXT'],
    [11,'physician_certification','TEXT'],
    [12,'ve_signature','TEXT'],
    [13,'systematic_callsign_change','TEXT'],
    [14,'vanity_callsign_change','TEXT'],
    [15,'vanity_relationship','TEXT'],
    [16,'previous_callsign','TEXT'],
    [17,'previous_operator_class','TEXT'],
    [18,'trustee_name','TEXT']
    ]

    schema['AM'] = AM_schema

    
    CO_schema = [
        [1,'record_type','TEXT'],
        [2,'uid','INTEGER'],
        [3,'uls_file_number','TEXT'],
        [4,'callsign','TEXT'],
        [5,'comment_date','TEXT'],
        [6,'description','TEXT'],
        [7,'status_code','TEXT'],
        [8,'status_date','TEXT']
    ]

    schema['CO'] = CO_schema

    EN_schema = [
        [1,'record_type','TEXT'],
        [2,'uid','INTEGER'],
        [3,'uls_file_number','TEXT'],
        [4,'ebf_number','TEXT'],
        [5,'callsign','TEXT'],
        [6,'entity_type','TEXT'],
        [7,'licensee_id','TEXT'],
        [8,'entity_name','TEXT'],
        [9,'first_name','TEXT'],
        [10,'middle_initial','TEXT'],
        [11,'last_name','TEXT'],
        [12,'suffix','TEXT'],
        [13,'phone','TEXT'],
        [14,'fax','TEXT'],
        [15,'email','TEXT'],
        [16, 'address','TEXT'],
        [17,'city','TEXT'],
        [18,'state','TEXT'],
        [19,'zip_code','TEXT'],
        [20, 'po_box','TEXT'],
        [21,'attn_line','TEXT'],
        [22,'sgin','TEXT'],
        [23,'frn','TEXT'],
        [24,'applicant_type_code','TEXT'],
        [25,'applicant_type_code_other','TEXT'],
        [26,'status_code','TEXT'],
        [27,'status_date','TEXT'],
        [28,'three_7_ghz_license_type','TEXT'],
        [29, 'linked_uid','INTEGER'],
        [30, 'linked_callsign','TEXT']
    ]
    schema['EN'] = EN_schema

    HD_schema = [
    [1,'record_type','TEXT'],
    [2,'uid','INTEGER'],
    [3,'uls_file_number','TEXT'],
    [4,'ebf_number','TEXT'],
    [5,'callsign','TEXT'],
    [6,'license_status','TEXT'],
    [7,'radio_service_code','TEXT'],
    [8,'grant_date','TEXT'],
    [9,'expired_date','TEXT'],
    [10,'cancellation_date','TEXT'],
    [11,'eligibility_rule_num','TEXT'],

    [13,'alien','TEXT'],
    [14,'alien_govt','TEXT'],
    [15,'alien_corp','TEXT'],
    [16,'alien_officer','TEXT'],
    [17,'alien_control','TEXT'],
    [18,'revoked','TEXT'],
    [19,'convicted','TEXT'],
    [20,'adjudged','TEXT'],

    [22,'common_carrier','TEXT'],
    [23,'non_common_carrier','TEXT'],
    [24,'private_comm','TEXT'],
    [25,'fixed','TEXT'],
    [26,'mobile','TEXT'],
    [27,'radiolocation','TEXT'],
    [28,'satellite','TEXT'],
    [29,'dev_sta_demo','TEXT'],
    [30,'interconn_service','TEXT'],
    [31,'certifier_first_name','TEXT'],
    [32,'certifier_mi','TEXT'],
    [33,'certifier_last_name','TEXT'],
    [34,'certifier_suffix','TEXT'],
    [35,'certifier_title','TEXT'],
    [36,'female','TEXT'],
    [37,'black_african','TEXT'],
    [38,'native_american','TEXT'],
    [39,'hawaiian','TEXT'],
    [40,'asian','TEXT'],
    [41,'white','TEXT'],
    [42,'hispanic','TEXT'],
    [43,'effective_date','TEXT'],
    [44,'last_action_date','TEXT'],
    [45,'auction_id','TEXT'],
    [46,'broadcast_reg_status','TEXT'],
    [47,'band_mgr_reg_status','TEXT'],
    [48,'broadcast_service_type','TEXT'],
    [49,'alien_ruling','TEXT'],
    [50,'licensee_name_change','TEXT'],
    [51,'whitespace_ind','TEXT'],
    [52,'op_performance_req_choice','TEXT'],
    [53,'op_performance_req_answer','TEXT'],
    [54,'discontinuation_of_service','TEXT'],
    [55,'regulatory_compliance','TEXT'],
    [56,'nine_hund_mhz_eligibility','TEXT'],
    [57,'nine_hund_mhz_transition_plan_cert','TEXT'],
    [58,'nine_hund_mhz_return_spec_cert','TEXT'],
    [59,'nine_hund_mhz_payment_cert','TEXT']
    ]
    schema['HD'] = HD_schema

    HS_schema = [
        [1,'record_type','TEXT'],
        [2,'uid','INTEGER'],
        [3,'uls_file_number','TEXT'],
        [4,'callsign','TEXT'],
        [5,'log_date','TEXT'],
        [6,'code','TEXT']
    ]

    schema['HS'] = HS_schema

    LA_schema = [
        [1,'record_type','TEXT'],
        [2,'uid','INTEGER'],
        [3,'callsign','TEXT'],
        [4,'attach_code','TEXT'],
        [5,'attach_desc','TEXT'],
        [6,'attach_date','TEXT'],
        [7,'attach_filename','TEXT'],
        [8,'action_performed','TEXT']
    ]

    schema['LA'] = LA_schema

    SC_schema = [
        [1,'record_type','TEXT'],
        [2,'uid','INTEGER'],
        [3,'uls_file_number','TEXT'],
        [4,'ebf_number','TEXT'],
        [5,'callsign','TEXT'],
        [6,'special_cond_type','TEXT'],
        [7,'special_cond_code','INTEGER'],
        [8,'status_code','TEXT'],
        [9,'status_date','TEXT']
    ]

    schema['SC'] = SC_schema

    SF_schema = [
        [1,'record_type','TEXT'],
        [2,'uid','INTEGER'],
        [3,'uls_file_number','TEXT'],
        [4,'ebf_number','TEXT'],
        [5,'callsign','TEXT'],
        [6,'lic_free_form_type','TEXT'],
        [7,'unique_lic_free_form_id','INTEGER'],
        [8,'sequence_num','INTEGER'],
        [9,'lic_free_form_cond','TEXT'],
        [10,'status_code','TEXT'],
        [11,'status_date','TEXT']
    ]

    schema['SF'] = SF_schema

    return schema

def parse_data(dest_unpacked: str | os.PathLike, schema: dict) -> dict:
    '''Creates pandas dataframe for each table and returns them as a dictionary of dataframes'''
    
    table_list = ['AM','CO','EN','HD','HS','LA','SC','SF']
    tables_to_clean = ['EN','HD','HS','LA','SC','SF']
    database_tables = {}

    for table_name in table_list:
        table = make_table(dest_unpacked, headers=schema[table_name], source_name=f'{table_name}.DAT')
        if table_name in tables_to_clean:
            table = clean_data(table)
        database_tables[table_name] = table

    return database_tables

def make_current_uid_table(conn, table_name: str = 'current_uid') -> None:
    '''
    Gets the most recent UID for a given callsign since callsigns can change owners over time
    This can be used in INNER JOINS with the other tables to get the most recent data for a 
    callsign. This table is required in order to create the ham_summary table
    
    '''
    conn.execute(f'drop table if exists {table_name}')
    conn.execute(
        f''' 
        create table {table_name} as 

        with base as (
            select 
            hd.uid
            ,hd.callsign 
            ,hd.effective_date 
            ,en.frn

            from HD as hd 
            join EN as en 
            on hd.uid = en.uid
        ),

        cte1 as (
            select *, row_number() over (partition by callsign order by effective_date desc) as recent_callsign
            from base
        )

        select uid, callsign, effective_date,frn from cte1 where recent_callsign=1
        '''
    )

def make_ham_summary_table(conn, table_name: str ='ham_summary') -> None:
    '''
    Creates a summary table of all callsigns. Each
    callsign appears once. In cases where a callsign has changed owners
    over time, the most recent owner (judged by effective date)
    is listed.    
    '''
    uid_table_exists = conn.execute("select count(*) from sqlite_master where type='table' and name='current_uid'").fetchall()[0][0]
    if uid_table_exists == 1:
        conn.execute(f'drop table if exists {table_name}')
        conn.execute(
            f'''
            create table {table_name} as

            select
            en.callsign 
            ,case when ocm.op_class_name is null then 'Club' else ocm.op_class_name end as operator_class
            ,am.region_code
            ,am.trustee_callsign 
            ,am.trustee_name
            ,en.entity_name 
            ,en.first_name 
            ,en.last_name 
            ,en.address 
            ,en.po_box
            ,en.city 
            ,en.state
            ,en.zip_code
            ,sm.status as license_status
            ,hd.grant_date 
            ,hd.effective_date
            ,hd.expired_date
            ,hd.cancellation_date

            from EN as en
            join HD as hd 
            on en.uid = hd.uid
            join current_uid as curr
            on curr.uid=en.uid
            left join AM as am 
            on am.uid = en.uid
            left join op_class_map as ocm 
            on am.operator_class = ocm.op_class_code
            left join status_map as sm 
            on hd.license_status=sm.status_code
            '''        
        )
    else:
        raise RuntimeError('"current_uid" table does not exist. Cannot create ham_summary table')
def make_dimension_tables(conn) -> None:
    '''
    Creates dimension tables to map 1-letter
    indicators for operator class and license
    status to more human-friendly names.
    '''
    conn.execute('drop table if exists op_class_map')
    conn.execute(
        '''
        create table op_class_map(
            op_class_code TEXT,
            op_class_name TEXT
        )
        '''
    )
    conn.execute(
        '''
        insert into op_class_map values
            ('A','Advanced'),
            ('E','Amateur Extra'),
            ('G','General'),
            ('N','Novice'),
            ('P','Technician Plus'),
            ('T','Technician')
        '''
    )
    conn.execute('drop table if exists status_map')
    conn.execute(
        '''
        create table status_map(
            status_code TEXT,
            status TEXT
        )
        '''
    )
    conn.execute(
        '''
        insert into status_map values
            ('A','Active'),
            ('C','Canceled'),
            ('E','Expired'),
            ('L','Pending Legal Status'),
            ('P','Parent Station Canceled'),
            ('T','Terminated'),
            ('X','Term Pending')
        '''
    )
    conn.execute('drop table if exists last_update')
    conn.execute(
        '''
        create table last_update(
            date_updated TEXT
        )
        '''
    )
    conn.execute(
        '''
        insert into last_update values
            (date('now'))
        '''
    )
def make_stats_table(conn):
    '''
    Build a stats table that will record current row counts
    for the raw data tables
    '''
    conn.execute('drop table if exists row_counts')
    conn.execute(
        '''
        create table row_counts as 

            select 
                (select count(*) from AM) as AM
                ,(select count(*) from CO) as CO
                ,(select count(*) from EN) as EN
                ,(select count(*) from HD) as HD
                ,(select count(*) from HS) as HS
                ,(select count(*) from LA) as LA
                ,(select count(*) from SC) as SC
                ,(select count(*) from SF) as SF
        '''
    )

def build_database(database_dir: str | os.PathLike, database_tables: dict, database_schema: dict, tables_to_update: list) -> None:
    '''Performs all create and update operations in the database'''
    create_scripts = make_create_scripts(database_schema)
    dtype_schemas = {}

    for table_name, schema in database_schema.items():
        dtype_dict = {}
        for row_number, column_name, data_type in schema:
            dtype_dict[column_name] = data_type
        dtype_schemas[table_name] = dtype_dict

    with sqlite3.connect(database_dir) as conn:

        for script in create_scripts:
            conn.execute(script)
        for table_name, table in database_tables.items():
            if table_name in tables_to_update:
                table.to_sql(table_name, conn, if_exists='replace',dtype=dtype_schemas[table_name],index=False)

        # no need to rebuild these tables if we didn't overwrite any source tables
        if len(tables_to_update) > 0:
            make_dimension_tables(conn)
            make_current_uid_table(conn)
            make_ham_summary_table(conn)

            make_stats_table(conn)

def main():

    # FCC URL should be stable, but other two are system specfic to the user
    url = 'https://data.fcc.gov/download/pub/uls/complete/l_amat.zip'

    # define path and filename where the .zip file should go
    # e.g. .../Downloads/ham.zip
    destination_string = '/home/matt/Downloads/ham.zip'

    # define path for your SQLite database file
    # e.g. .../fcc_ham.db
    database_dir_string = '/home/matt/fcc_ham.db'


    dest_unpacked_string = destination_string.replace('.zip','') 

    # leverage pathlib so this script works across platforms
    destination = Path(destination_string)
    dest_unpacked = Path(dest_unpacked_string)
    database_dir = Path(database_dir_string)

    clean_temp_files(destination, dest_unpacked)
    get_database(url, destination)
    unpack_data_files(destination, dest_unpacked)

    database_schema = define_schema()
    database_tables = parse_data(dest_unpacked, database_schema)
    tables_to_update = data_qc(database_dir, new_tables=database_tables)
    build_database(database_dir, database_tables, database_schema, tables_to_update)


if __name__ == '__main__':
    main()