# keepass-to-lastpass

A Python script for modifying the XML exported from KeePass to LastPass for
built-in types.

## Supported LastPass Built-In Item Types

- __Database__
- __Server__

If a URL is specified for a password entry in KeePass, it is automatically
imported as a website.

## Process

- Remove history items for each password entry
- Delete `Sample Entry` items created by KeePass
- Use item templates to transform KeePass entries to one of the supported
  LastPass item types
- Convert all remaining items that do not require customization to LastPass
  database items
  
> Even though this script renames the root group folder,
> LastPass does not allow you to import passwords directly into shared folders.
> The import process does allow you to continue, however.

### Entry Modification Details

- Retrieve the values for the five standard KeePass fields for safe keeping:
  - `Notes`
  - `Password`
  - `Title`
  - `URL`
  - `UserName`

- Stop here if the `Notes` start with `NoteType:`, which means it already has
  been modified; prevents "re-fixing" XML
- Replace tabs in the entry title with a single space
- Saves the standard KeePass fields in the entry template dictionary object
- Assumes the standard `URL` field is a `Hostname` if part of the template and
  no default value is specified
- Converts the entry template dictionary to a string for the `Notes` field
- Converts tabs in the `Notes` field to a single space
- Updates the `Notes` and `Title` fields
- Remove any `<String>` objects from the entry which are added to the `Notes`
  field by default on import if they are unused by the LastPass item type; this
  prevents passwords from being visible in the entry notes

The entry templates essentially collect all of the available fields in a
LastPass item type, like `Database`, and then put them in the `Notes` field one
line at a time, starting with the field name, a colon, and then the value. The
last field should be `Notes`, as notes may use multiple lines and characters.
A sample template could look like this:

```text
NoteType:Database
Language:en-US
Type:Oracle
Hostname:database_host_name
Port:1521
Database:for_oracle_a_service_name
Username:some_username
Password:some_password
SID:
Alias:
Notes:Some note text can go here
```

This is confirmed by the tests performed by the [official LastPass CLI](https://github.com/lastpass/lastpass-cli/blob/master/test/tests)
in GitHub, and additionally by the format presented when items are exported from
LastPass.
