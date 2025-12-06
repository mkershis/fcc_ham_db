# This script scrapes the entire FCC ham radio database from the web
# and builds a MySQL database. Also does some data cleaning, creates
# a useful summary table  containing the most recent callsign owner's
# information, and creates indexes to boost performance

import requests, zipfile, os, shutil
from pathlib import Path
import numpy as np 
import pandas as pd
from sqlalchemy import create_engine, sql, types
import time



##########################################################################################
#                                                                                        #
#                     Variables to Edit Before Running                                   #
#                                                                                        #
##########################################################################################

# FCC URL should be stable, but other two are system specfic to the user
url = 'https://data.fcc.gov/download/pub/uls/complete/l_amat.zip'
destination_string = '' # temporary location for unpacking the zip files
database_dir = ''      # should be the connection string to your mysql instance. For a local DB: e.g. 'mysql+pymysql://<USERNAME>:<PASSWORD>@localhost:3306'
db_name = ''           # name of your database e.g. 'fcc_ham'

engine = create_engine(database_dir)
# before doing anything, make sure the database exists and create it if not!
with engine.connect() as conn:
    conn.execute(sql.text(f'create database if not exists {db_name}'))
    conn.commit()

db_conn_string = f'{database_dir}/{db_name}'



dest_unpacked_string = destination_string.replace('.zip','') 

# leverage pathlib so this script works across platforms
destination = Path(destination_string)
dest_unpacked = Path(dest_unpacked_string)

def define_schema():
    '''
    Defines the postition, column name, and datatype for fields in each table
    '''
    schema = {}

    AM_schema = [
        [1, 'record_type',types.CHAR(2)],
        [2, 'uid',types.NUMERIC(9,0)],
        [3, 'uls_number',types.CHAR(14)],
        [4, 'ebf_number',types.VARCHAR(30)],
        [5, 'callsign',types.CHAR(10)],
        [6, 'operator_class',types.CHAR(1)],
        [7, 'group_code', types.CHAR(1)],
        [8, 'region_code', types.INTEGER()],
        [9, 'trustee_callsign',types.CHAR(10)],
        [10, 'trustee_indicator',types.CHAR(1)],
        [11, 'physician_certification',types.CHAR(1)],
        [12, 've_signature',types.CHAR(1)],
        [13, 'systematic_callsign_change',types.CHAR(1)],
        [14, 'vanity_callsign_change',types.CHAR(1)],
        [15, 'vanity_relationship',types.CHAR(12)],
        [16, 'previous_callsign', types.CHAR(10)],
        [17, 'previous_operator_class',types.CHAR(1)],
        [18, 'trustee_name',types.VARCHAR(50)]
    ]

    schema['am'] = AM_schema

    CO_schema = [
        [1, 'record_type',types.CHAR(2)],
        [2, 'uid',types.NUMERIC(9,0)],
        [3, 'uls_number',types.CHAR(14)],
        [4, 'callsign',types.CHAR(10)],
        [5, 'comment_date',types.DATE()],
        [6, 'description',types.VARCHAR(255)],
        [7,'status_code',types.CHAR(1)],
        [8, 'status_date',types.DATE()]
    ]

    schema['co'] = CO_schema

    EN_schema = [
        [1,'record_type',types.CHAR(2)],
        [2,'uid',types.NUMERIC(9,0)],
        [3,'uls_file_number',types.CHAR(14)],
        [4,'ebf_number',types.VARCHAR(30)],
        [5,'callsign',types.CHAR(10)],
        [6,'entity_type',types.CHAR(2)],
        [7,'licensee_id',types.CHAR(9)],
        [8,'entity_name',types.VARCHAR(200)],
        [9,'first_name',types.VARCHAR(20)],
        [10,'middle_initial',types.CHAR(1)],
        [11,'last_name',types.VARCHAR(20)],
        [12,'suffix',types.CHAR(3)],
        [13,'phone',types.CHAR(10)],
        [14,'fax',types.CHAR(10)],
        [15,'email',types.VARCHAR(50)],
        [16, 'address',types.VARCHAR(60)],
        [17,'city',types.VARCHAR(20)],
        [18,'state',types.CHAR(2)],
        [19,'zip_code',types.CHAR(9)],
        [20, 'po_box',types.VARCHAR(20)],
        [21,'attn_line',types.VARCHAR(35)],
        [22,'sgin',types.CHAR(3)],
        [23,'frn',types.CHAR(10)],
        [24,'applicant_type_code',types.CHAR(1)],
        [25,'applicant_type_code_other',types.CHAR(40)],
        [26,'status_code',types.CHAR(1)],
        [27,'status_date',types.DATE()],
        [28,'three_7_ghz_license_type',types.CHAR(1)],
        [29, 'linked_uid',types.NUMERIC(9,0)],
        [30, 'linked_callsign',types.CHAR(10)]
    ]
    schema['en'] = EN_schema

    HD_schema = [
    [1,'record_type',types.CHAR(2)],
    [2,'uid',types.NUMERIC(9,0)],
    [3,'uls_file_number',types.CHAR(14)],
    [4,'ebf_number',types.VARCHAR(30)],
    [5,'callsign',types.CHAR(10)],
    [6,'license_status',types.CHAR(1)],
    [7,'radio_service_code',types.CHAR(2)],
    [8,'grant_date',types.DATE()],
    [9,'expired_date',types.DATE()],
    [10,'cancellation_date',types.DATE()],
    [11,'eligibility_rule_num',types.CHAR(10)],

    [13,'alien',types.CHAR(1)],
    [14,'alien_govt',types.CHAR(1)],
    [15,'alien_corp',types.CHAR(1)],
    [16,'alien_officer',types.CHAR(1)],
    [17,'alien_control',types.CHAR(1)],
    [18,'revoked',types.CHAR(1)],
    [19,'convicted',types.CHAR(1)],
    [20,'adjudged',types.CHAR(1)],

    [22,'common_carrier',types.CHAR(1)],
    [23,'non_common_carrier',types.CHAR(1)],
    [24,'private_comm',types.CHAR(1)],
    [25,'fixed',types.CHAR(1)],
    [26,'mobile',types.CHAR(1)],
    [27,'radiolocation',types.CHAR(1)],
    [28,'satelite',types.CHAR(1)],
    [29,'dev_sta_demo',types.CHAR(1)],
    [30,'interconn_service',types.CHAR(1)],
    [31,'certifier_first_name',types.VARCHAR(20)],
    [32,'certifier_mi',types.CHAR(1)],
    [33,'certifier_last_name',types.VARCHAR(20)],
    [34,'certifier_suffix',types.CHAR(3)],
    [35,'certifier_title',types.CHAR(40)],
    [36,'female',types.CHAR(1)],
    [37,'black_african',types.CHAR(1)],
    [38,'native_american',types.CHAR(1)],
    [39,'hawaiian',types.CHAR(1)],
    [40,'asian',types.CHAR(1)],
    [41,'white',types.CHAR(1)],
    [42,'hispanic',types.CHAR(1)],
    [43,'effective_date',types.DATE()],
    [44,'last_action_date',types.DATE()],
    [45,'auction_id',types.INTEGER()],
    [46,'broadcast_reg_status',types.CHAR(1)],
    [47,'band_mgr_reg_status',types.CHAR(1)],
    [48,'broadcast_service_type',types.CHAR(1)],
    [49,'alien_ruling',types.CHAR(1)],
    [50,'licensee_name_change',types.CHAR(1)],
    [51,'whitespace_ind',types.CHAR(1)],
    [52,'op_performance_req_choice',types.CHAR(1)],
    [53,'op_performance_req_answer',types.CHAR(1)],
    [54,'discontinuation_of_service',types.CHAR(1)],
    [55,'regulatory_compliance',types.CHAR(1)],
    [56,'nine_hund_mhz_eligibility',types.CHAR(1)],
    [57,'nine_hund_mhz_transition_plan_cert',types.CHAR(1)],
    [58,'nine_hund_mhz_return_spec_cert',types.CHAR(1)],
    [59,'nine_hund_mhz_payment_cert',types.CHAR(1)]
    ]
    schema['hd'] = HD_schema

    HS_schema = [
        [1,'record_type',types.CHAR(2)],
        [2,'uid',types.NUMERIC(9,0)],
        [3,'uls_file_number',types.CHAR(14)],
        [4,'callsign',types.CHAR(10)],
        [5,'log_date',types.DATE()],
        [6,'code',types.CHAR(6)]
    ]

    schema['hs'] = HS_schema

    LA_schema = [
        [1,'record_type',types.CHAR(2)],
        [2,'uid',types.NUMERIC(9,0)],
        [3,'callsign',types.CHAR(10)],
        [4,'attach_code',types.CHAR(1)],
        [5,'attach_desc',types.VARCHAR(60)],
        [6,'attach_date',types.DATE()],
        [7,'attach_filename',types.VARCHAR(60)],
        [8,'action_performed',types.CHAR(1)]
    ]

    schema['la'] = LA_schema

    SC_schema = [
        [1,'record_type',types.CHAR(2)],
        [2,'uid',types.NUMERIC(9,0)],
        [3,'uls_file_number',types.CHAR(14)],
        [4,'ebf_number',types.VARCHAR(30)],
        [5,'callsign',types.CHAR(10)],
        [6,'special_cond_type',types.CHAR(1)],
        [7,'special_cond_code',types.INTEGER()],
        [8,'status_code',types.CHAR(1)],
        [9,'status_date',types.DATE()]
    ]

    schema['sc'] = SC_schema

    SF_schema = [
        [1,'record_type',types.CHAR(2)],
        [2,'uid',types.NUMERIC(9,0)],
        [3,'uls_file_number',types.CHAR(14)],
        [4,'ebf_number',types.VARCHAR(30)],
        [5,'callsign',types.CHAR(10)],
        [6,'lic_free_form_type',types.CHAR(1)],
        [7,'unique_lic_free_form_id',types.NUMERIC(9,0)],
        [8,'sequence_num',types.INTEGER],
        [9,'lic_free_form_cond',types.VARCHAR(255)],
        [10,'status_code',types.CHAR(1)],
        [11,'status_date',types.DATE()]
    ]

    schema['sf'] = SF_schema

    return schema


def clean_temp_files(destination: str | os.PathLike, dest_unpacked: str | os.PathLike) -> None:
    '''Do a little housekeeping to remove old versions of these files'''
    if os.path.isdir(dest_unpacked):
        shutil.rmtree(dest_unpacked)
    if os.path.isfile(destination):
        os.remove(destination)

def get_database(url: str) -> None:
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
    
    # Data quality checking. Replace any value which doesn't
    # fit the defined schema with a null value. Preferable to 
    for col_num, column, dtype in headers:
        if column not in df.columns:
            continue

        if isinstance(dtype, types.CHAR) or isinstance(dtype, types.VARCHAR):
            max_len = dtype.length
            valid = df[column].str.len().le(max_len) | df[column].isna()
            df[column] = df[column].where(valid)

        elif isinstance(dtype, types.Integer):
            df[column] = pd.to_numeric(df[column], errors='coerce')
        elif isinstance(dtype, types.NUMERIC):
            precision = dtype.precision
            scale = dtype.scale
            df[column] = pd.to_numeric(df[column],errors='coerce')

            if scale is not None and precision is not None:
                
                digits_before = precision - scale 
                max_val = 10**digits_before - 10**(-scale)
                valid = df[column].abs().le(max_val) | df[column].isna()
                df[column] = df[column].where(valid)
        elif isinstance(dtype, types.DATE):
            df[column] = pd.to_datetime(df[column], errors='coerce')

        # do a little normalize of first/last names to title case
        # state abbreviations to upper case
        if column in ['first_name','last_name']:
            df[column] = df[column].str.title()
        if column == 'state':
            df[column] = df[column].str.upper()
    return df


def parse_data(dest_unpacked: str | os.PathLike, schema: dict) -> dict:
    '''Creates pandas dataframe for each table and returns them as a dictionary of dataframes'''
    database_tables = {}

    AM = make_table(dest_unpacked, headers=schema['am'], source_name='AM.DAT')
    database_tables['am'] = AM

    CO = make_table(dest_unpacked, headers=schema['co'], source_name = 'CO.DAT')
    database_tables['co'] = CO

    EN = make_table(dest_unpacked, headers=schema['en'], source_name='EN.DAT')
    database_tables['en'] = EN

    HD = make_table(dest_unpacked, headers=schema['hd'],source_name='HD.DAT')
    database_tables['hd'] = HD

    HS = make_table(dest_unpacked, headers=schema['hs'], source_name='HS.DAT')
    database_tables['hs']=HS

    LA = make_table(dest_unpacked,headers=schema['la'], source_name = 'LA.DAT')
    database_tables['la'] = LA

    SC = make_table(dest_unpacked, headers=schema['sc'],source_name = 'SC.DAT')
    database_tables['sc'] = SC

    SF = make_table(dest_unpacked, headers=schema['sf'], source_name = 'SF.DAT')
    database_tables['sf'] = SF
    return database_tables

def build_database(db_conn_string: str, database_tables:dict , database_schema: dict) -> None:
    dtype_schemas = {}
    for table_name, schema in database_schema.items():
        dtype_dict = {}
        for row_number, column_name, data_type in schema:
            dtype_dict[column_name] = data_type
        dtype_schemas[table_name] = dtype_dict
    
    db_engine = create_engine(db_conn_string)

    with db_engine.connect() as conn:
        for table_name, table in database_tables.items():
            try:
                current_count = conn.execute(sql.text(f'select count(*) from {table_name}')).fetchall()[0][0]
            except:
                # will get an error if table doesn't exist, in which case we can 
                # set current_count = 0 to ensure we will create the table
                current_count = 0
            # we only want to overwrite the table if the new table is at least the same
            # size or greater than the current one
            if len(table) >= current_count:
                print(f'Preparing to update "{table_name}"...')
                table.to_sql(table_name, conn, if_exists='replace',index=False, dtype=dtype_schemas[table_name])
                if 'uid' in table.columns:
                    conn.execute(sql.text(f'create index idx_uid on {table_name}(uid)'))
                
                if 'callsign' in table.columns:
                    conn.execute(sql.text(f'create index idx_callsign on {table_name}(callsign)'))
                
                if 'trustee_callsign' in table.columns:
                    conn.execute(sql.text(f'create index idx_trustee_callsign on {table_name}(trustee_callsign)'))
                conn.commit()
                print(f'\tTable "{table_name}" was updated')
            else:
                print(f'Table "{table_name}" was not updated. ')

def build_summary(db_conn_string):
    '''Creates a useful summary table with one row per callsign (most recent callsign owner)'''
    db_engine = create_engine(db_conn_string)

    with db_engine.connect() as conn:

        conn.execute(sql.text('drop table if exists summary'))
        conn.commit()
        create_script = '''
        create table summary as 

        with base_uid as (
            select hd.uid
            ,hd.callsign 
            ,hd.effective_date 
            ,en.frn 
            from hd as hd 
            join en as en 
            on hd.uid = en.uid
        ),
        cte1 as (
            select *, row_number() over (partition by callsign order by effective_date desc) as recent_rn 
            from base_uid
        ),
        current_owner as (
            select uid from cte1 where recent_rn = 1
        )

        select
        en.callsign 
        ,case when am.operator_class = 'A' then 'Advanced'
            when am.operator_class = 'E' then 'Extra'
            when am.operator_class = 'G' then 'General'
            when am.operator_class = 'N' then 'Novice'
            when am.operator_class = 'P' then 'Technician Plus'
            when am.operator_class = 'T' then 'Technician'
            when am.operator_class is null then 'Club'
            else 'Unknown' end as operator_class
            
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
        ,hd.grant_date
        ,hd.effective_date
        ,hd.expired_date
        ,hd.cancellation_date

        from en as en 
        join hd as hd 
        on en.uid = hd.uid
        join current_owner as c
        on c.uid = en.uid
        left join am as am 
        on am.uid = en.uid
        ''' 
        conn.execute(sql.text(create_script))
        conn.execute(sql.text('create index idx_callsign on summary(callsign)'))
        conn.execute(sql.text('create index idx_last_name on summary(last_name)'))
        conn.execute(sql.text('create index idx_city on summary(city)'))
        conn.execute(sql.text('create index idx_state on summary(state)'))
        conn.commit()         

def main():
    # clean_temp_files(destination, dest_unpacked)
    # get_database(url)
    # unpack_data_files(destination, dest_unpacked)

    database_schema = define_schema()
    database_tables = parse_data(dest_unpacked, database_schema)
    build_database(db_conn_string, database_tables, database_schema)
    build_summary(db_conn_string)

if __name__ == '__main__':
    start_time = time.time()
    main()
    end_time = time.time()

    runtime = end_time - start_time
    runtime_min = round(runtime / 60, 1)
    print(f'Process completed in {runtime_min} minutes.')
