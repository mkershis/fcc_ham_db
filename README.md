## fcc_ham_db
This is a Python script which downloads the entire FCC ham radio callsign database (multiple tables) and creates a local copy on your computer using SQLite3. After the initial run, the script can be run again because it essentially performs a "kill and fill" update (i.e. subsequent runs will drop existing tables and populate the data from scratch).

The source of the data is from the [FCC website](https://www.fcc.gov/uls/transactions/daily-weekly) and is specifically the `l_amat.zip` file under the **Weekly Databases > Licenses** section. 

Detailed information about the database schema and defintitions can be found [here](https://www.fcc.gov/wireless/data/public-access-files-database-downloads), but below I'll describe a few additional tables which are created as part of the script. The motivation in creating these tables is to make the data a bit more user-friendly to browse. 

* `current_uid` - this table lists the most current Unique System Identifier, callsign, effective date, and FRN number for a given callsign. Since the database captures all transactions and since callsigns can change owners over time, this table ensures that searching for a given callsign returns the most recent owner as judged by effective date
* `op_class_map` - simple dimension table to map the one-letter license codes to their full string names
* `status_map` - dimension table to map one-letter licenses statuses to full string names
* `ham_summary` - leverages the above three tables to extract the most recent metadata for a given callsign and puts the results in a single table. This is probably the easiest table to work with if you want to look up a callsign. Also includes the trustee name and callsign for clubs.
* `row_counts` - saves row counts for the current database load. This table will be queried upon re-running the script to ensure that we only write tables if the record counts are greater than or equal to the current table size
* `last_update` - stores a single date reflecting when the database was last built

**IMPORTANT:** Before running the script for the first time, open the file and add values for the following paths which are specific to your system:

* `destination_string` - this should be the full path and filename of where you want to temporarily download the raw datafiles before building the SQL database. An example might be `.../Downloads/ham.zip`
* `database_dir_string` - this should be full path of the SQLite database you wish to create. It should point to a prefered location on your machine and should end in .db. An example might be `...\<directory_for_your_database>\fcc_ham.db`
