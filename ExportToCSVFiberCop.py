import traceback
import arcpy
import os, codecs
import uuid
import zipfile
from datetime import datetime
import uuid

# Global variables
out_folder = None

# Detect environment
PRODUCT_NAME = arcpy.GetInstallInfo()['ProductName']
IS_SERVER = PRODUCT_NAME == 'Server'
IS_PRO = PRODUCT_NAME == 'ArcGISPro'

# Fields to evaluate in Fibercop addresses layer
FIELD_PAIRS = [
    ("civico", "civico_new"),
    ("barrato", "barratonew"),
    ("indirizzo", "indirizo_new"),
    ("particella", "particel_1"),
    ("via", "via_new")
]
COLUMNS_TO_REMOVE = ["al_total", "tot_uni_im"] + [pair[1] for pair in FIELD_PAIRS]

# Function for measuting times
def add_message(message):
    now = datetime.now()
    formatted_date = now.strftime("%Y-%m-%d %H:%M:%S")
    arcpy.AddMessage("{} | {}".format(formatted_date, message))

# Function to handle Unicode transformation
def unicodify(row_val):
    return str(row_val) if row_val is not None else ''

# Get the name of the ObjectID field dynamically
def get_objectid_field_name(layer):
    return arcpy.Describe(layer).OIDFieldName

# Check and validate the fields in 'FIELDS_ADDR' for 'ADDRESS_LAYER'
def validate_fields(layer, fields):
    layer_fields = [field.name for field in arcpy.ListFields(layer)]
    missing_fields = [field for field in fields if field not in layer_fields]
    if missing_fields:
        arcpy.AddError("The following fields are missing in the address layer: {}".format(", ".join(missing_fields)))
        return False
    return True

def generate_unique_filename(name_str, extension="zip"):
    if name_str:
        unique_name = "{}_{}.{}".format(name_str, uuid.uuid4(), extension)
    else:
        unique_name = "{}.{}".format(uuid.uuid4(), extension)
    return os.path.join(arcpy.env.scratchFolder, unique_name)

def create_zip_from_files(files, zip_path):
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for file in files:
            zipf.write(file, os.path.basename(file))  # Add files to the zip with their basename
    arcpy.AddMessage("Created ZIP archive: {}".format(zip_path))

def get_field_domains(layer_desc):
    field_domains = {}
    workspace = os.path.dirname(layer_desc.catalogPath) if layer_desc.catalogPath else arcpy.env.workspace
    if not workspace:
        raise ValueError("Workspace for the layer could not be determined.")

    domain_list = arcpy.da.ListDomains(workspace)
    for field in layer_desc.fields:
        if field.domain:
            domain = next((d for d in domain_list if d.name == field.domain), None)
            if domain and domain.domainType == "CodedValue":
                field_domains[field.name] = domain.codedValues

    return field_domains

def resolve_field_value(row, field_new_index, field_original_index):
    new_value = row[field_new_index] if row[field_new_index] not in [None, '', ' '] else None
    return new_value if new_value is not None else row[field_original_index]

# Función para reemplazar valores de dirección "SNC" o 0 con un valor único
def generate_unique_address_value():
    return str(uuid.uuid4())  # Genera un valor único usando UUID

def get_field_domains(layer_desc):
    field_domains = {}
    workspace = os.path.dirname(layer_desc.catalogPath) if layer_desc.catalogPath else arcpy.env.workspace
    if not workspace:
        raise ValueError("Workspace for the layer could not be determined.")

    domain_list = arcpy.da.ListDomains(workspace)
    for field in layer_desc.fields:
        if field.domain:
            domain = next((d for d in domain_list if d.name == field.domain), None)
            if domain and domain.domainType == "CodedValue":
                field_domains[field.name] = domain.codedValues

    return field_domains


def fcl_to_csv(fcl, csv_path, fields, custom_names):
    try:
        output_dir = os.path.dirname(csv_path)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        layer_desc = arcpy.Describe(fcl)
        field_domains = get_field_domains(layer_desc)

        header_fields = [name for name, field in zip(custom_names, fields) if field not in COLUMNS_TO_REMOVE]

        with codecs.open(csv_path, "w", encoding="UTF-8") as f:
            header_fields = header_fields[:-1] + ["Units", "X", "Y"]
            f.write(";".join(header_fields) + os.linesep)

            with arcpy.da.SearchCursor(fcl, fields + ["SHAPE@"]) as cursor:
                for row in cursor:
                    shape = row[-1]  # Extract geometry
                    x, y = shape.firstPoint.X, shape.firstPoint.Y

                    valid_fields = [field for field in fields if field not in COLUMNS_TO_REMOVE]

                    data_row = []
                    for field in valid_fields:
                        field_value = row[fields.index(field)]
                        if field in field_domains:
                            data_row.append(field_domains[field].get(field_value, field_value))
                        else:
                            data_row.append(field_value)

                    # Eliminar SHAPE@ de data_row
                    data_row = data_row[:-1]

                    # Process field values based on FIELD_PAIRS
                    for original, new in FIELD_PAIRS:
                        if original in fields and new in fields:
                            original_idx = fields.index(original)
                            new_idx = fields.index(new)
                            data_row[original_idx] = resolve_field_value(row, new_idx, original_idx)

                    civico_idx = fields.index("civico") if "civico" in fields else None
                    if civico_idx is not None and data_row[civico_idx] in {"SNC", "0", None}:
                        data_row[civico_idx] = generate_unique_address_value()

                    # Handle pnrr and status fields
                    if "pnrr" in valid_fields and "status" in valid_fields:
                        pnrr_index = valid_fields.index("pnrr")
                        status_index = valid_fields.index("status")
                        status_field_name = valid_fields[status_index]

                        if row[pnrr_index] == '0':
                            domain_value = '1'
                        elif row[pnrr_index] == '1':
                            domain_value = '6'
                        else:
                            domain_value = None

                        if domain_value is not None and status_field_name in field_domains:
                            coded_values = field_domains[status_field_name]
                            domain_name = coded_values.get(str(domain_value), None)
                            if domain_name is not None:
                                data_row[status_index] = domain_name
                            else:
                                data_row[status_index] = domain_value

                    # Determinar el valor más alto entre los dos campos
                    tot_uni_idx = fields.index("tot_uni_im") if "tot_uni_im" in fields else None
                    al_total_idx = fields.index("al_total") if "al_total" in fields else None

                    # Manejo robusto de valores
                    def get_int_value(value):
                        if value is None:
                            return 0
                        try:
                            return int(str(value).strip() or 0)
                        except ValueError:
                            return 0

                    # Obtén los valores numéricos de las columnas
                    units_value = max(
                        get_int_value(row[tot_uni_idx]) if tot_uni_idx is not None else 0,
                        get_int_value(row[al_total_idx]) if al_total_idx is not None else 0
                    )

                    # Filtrar registros con valor 0
                    if units_value == 0:
                        continue


                    # Agregar la columna "Units" al data_row
                    data_row.append(units_value)

                    data_row.extend([x, y])  # Add X, Y coordinates
                    f.write(";".join(map(str, data_row)) + os.linesep)


        arcpy.AddMessage("Export completed: {}".format(csv_path))
        return csv_path

    except Exception as e:
        arcpy.AddError("Error exporting to CSV: {}".format(e))
        arcpy.AddError(traceback.format_exc())


# Main function to execute the tool
def script_tool(poly_lyr, field_name, addr_lyr, fld_addr, out_dir, custom_names, selected_polygon):
    global selected_polygons
    selected_polygons = selected_polygon

    try:
        # Autenticación
        if arcpy.GetSigninToken():
            arcpy.AddMessage("Authenticated successfully.")
        else:
            raise ValueError("Authentication failed: no session provided.")

        # Validar capas de entrada
        if not (arcpy.Exists(poly_lyr) and arcpy.Exists(addr_lyr)):
            raise ValueError("One or more input layers are invalid or do not exist.")

        # Crear capas temporales
        polygon_layer_name = "temp_polygon_layer"
        address_layer_name = "temp_address_layer"
        arcpy.MakeFeatureLayer_management(poly_lyr, polygon_layer_name)
        arcpy.MakeFeatureLayer_management(addr_lyr, address_layer_name)

        oid_field = get_objectid_field_name(polygon_layer_name)

        # Selección de polígonos
        if selected_polygons:
            selected_polygons = [str(int(oid)) for oid in selected_polygons.split(',') if oid.strip().isdigit()]

            selection_query = "{} IN ({})".format(oid_field, ', '.join(selected_polygons))
            arcpy.AddMessage("Selected polygons: {}".format(selected_polygons))

        else:
            selected_polygons = [row[0] for row in arcpy.da.SearchCursor(polygon_layer_name, [oid_field])]
            selection_query = "{} IN ({})".format(oid_field, ', '.join(map(str, selected_polygons)))
            arcpy.AddMessage("No explicit selection. Using all polygons.")

        arcpy.SelectLayerByAttribute_management(polygon_layer_name, "NEW_SELECTION", selection_query)

        # Validar campos de direcciones
        if not validate_fields(address_layer_name, fld_addr):
            raise ValueError("Some required address fields are missing.")

        output_files = []

        # Iterar por cada polígono seleccionado
        for polygon_oid in selected_polygons:
            arcpy.SelectLayerByAttribute_management(polygon_layer_name, "NEW_SELECTION", "{} = {}".format(oid_field, polygon_oid))

            # Obtener el nombre del polígono
            with arcpy.da.SearchCursor(polygon_layer_name, [field_name]) as cursor:
                polygon_name = next(cursor, [None])[0]
                if not polygon_name:
                    raise ValueError("The field '{}' is empty or invalid for polygon {}.".format(field_name, polygon_oid))

            # Crear archivo CSV
            filename = "{}.csv".format(polygon_name)
            filepath = os.path.join(out_dir, filename) if not IS_SERVER else generate_unique_filename(filename, "csv")

            arcpy.SelectLayerByLocation_management(address_layer_name, "WITHIN", polygon_layer_name)
            address_count = int(arcpy.GetCount_management(address_layer_name).getOutput(0))

            if address_count > 0:
                arcpy.AddMessage("Creating {}, total addresses={} for polygon {}".format(filepath, address_count, polygon_name))
                fcl_to_csv(address_layer_name, filepath, fld_addr, custom_names)
                output_files.append(filepath)
            else:
                arcpy.AddMessage("No addresses found for polygon {} (OID: {})".format(polygon_name, polygon_oid))

        # Manejo de salida para entorno servidor
        if IS_SERVER and output_files:
            zip_path = generate_unique_filename("output", "zip")
            create_zip_from_files(output_files, zip_path)
            arcpy.SetParameterAsText(9, zip_path)

        arcpy.AddMessage("Export completed successfully.")

    except Exception as e:
        arcpy.AddError("Error in script execution: {}".format(e))
        arcpy.AddError(traceback.format_exc())

    finally:
        # Limpiar capas temporales
        for layer in (polygon_layer_name, address_layer_name):
            if arcpy.Exists(layer):
                arcpy.Delete_management(layer)


def transform_field_address_names(field_address_names):
    pairs = field_address_names.split(';')
    field_address = []
    custom_names = []

    for pair in pairs:
        elements = pair.split(" ", 1)
        if len(elements) == 2:
            field = elements[0]
            name = elements[1].strip() 
            if name.startswith("'") and name.endswith("'"):
                name = name[1:-1] 

            field_address.append(field)
            custom_names.append(name)

    return field_address, custom_names


# Entry point for script execution
if __name__ == "__main__":
    # Retrieve parameters as global variables
    polygon_layer = arcpy.GetParameter(0)
    field_name = arcpy.GetParameterAsText(1)
    address_layer = arcpy.GetParameter(2)
    field_address_names = str(arcpy.GetParameter(3)) # Assumes value-table parameter
    out_folder = arcpy.GetParameterAsText(4)
    use_auth = arcpy.GetParameterAsText(5).lower() == 'true'
    url_portal = arcpy.GetParameterAsText(6)
    username = arcpy.GetParameterAsText(7)
    password = arcpy.GetParameterAsText(8)
    selected_polygon = arcpy.GetParameterAsText(10)
    field_address_names_rest = str(arcpy.GetParameter(11))
    field_address, custom_names = transform_field_address_names(field_address_names_rest if field_address_names_rest else field_address_names)

    arcpy.AddMessage(selected_polygon)

    # Execute the script tool
    script_tool(polygon_layer, field_name, address_layer, field_address, out_folder, custom_names, selected_polygon)
