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

**IMPORTANT:** Before running the script for the first time, you should create a `config.toml` file and place it in the same directory as this script. The contents of the file should be as follows:

```
download_destination = "<<path where you want the data downloaded>>"
database_location = "<<directory where you want the database>>"
```

The `download_destination` is where the script will download the .zip file from the FCC and is also where the contents will be unpacked. The .zip file will be called `ham.zip` and will be simply unzipped to a folder called `ham`. Similarly the `database_location` is where the script will write the final database file called `fcc_ham.db`.

Now, if you do not create a config.toml file, then the script will default to downloading the raw data to your Downloads folder and will save the database to your home directory. You can always move this around later if you want. Note that, as of this writing in April 2026, the FCC database file is over 1.2 GB in size, so make sure you have enough disk space wherever you decide to save it.