from flask import Flask, render_template, make_response, url_for, request, redirect
from google.auth import compute_engine
from google.cloud import storage
import copy as cp
import json
# from flask_firebase import FirebaseAuth update
import firebase_admin.auth as auth
from firebase_admin import credentials
# from firebase_admin import storage as strg
import firebase_admin
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import ee
import numpy as np
import cv2
import csv
import pandas as pd
import seaborn as sns
import os
from flask_sqlalchemy import SQLAlchemy
from staticmap import StaticMap, Polygon
import shutil
import simplejson
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__, static_url_path='/static')                #telling flask our script file name and static folder for use
app.wsgi_app = ProxyFix(
    app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1
)
# app.config['FIREBASE_API_KEY'] = "AIzaSyBzsRUiJQgSxc-hlV-zJCCLP95fpFIpSpY"
# app.config['FIREBASE_PROJECT_ID'] = "crop-monitoring-platform"
# app.config['FIREBASE_AUTH_SIGN_IN_OPTIONS'] = 'google,email' # <-- coma separated list, see Providers above
app.config['SECRET_KEY'] = 'HYDE_JEKYLL' # <-- random string


# db_user = os.environ.get("DB_USER")
# db_pass = os.environ.get("DB_PASS")
# db_name = os.environ.get("DB_NAME")
# cloud_sql_connection_name = os.environ.get("CLOUD_SQL_CONNECTION_NAME")
db_user = 'client'
db_pass = '123456'
db_name = 'my_db'
cloud_sql_connection_name = 'instant-node-238517:europe-west1:vault-cold'

# app.config["SQLALCHEMY_DATABASE_URI"]= f"mysql+pymysql://root:{db_pass}@/{db_name}?unix_socket=/cloudsql/{cloud_sql_connection_name}"

# app.config["GOOGLE_APPLICATION_CREDENTIALS"]="instant-node-238517-firebase-adminsdk-tiqdt-a7fbecd401.json"

basedir = os.path.abspath(os.path.dirname(__file__))
db_uri = 'sqlite:///' + os.path.join(basedir, 'database.db')
app.config["SQLALCHEMY_DATABASE_URI"]= db_uri
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"]= False
keyfilepath=os.path.join(basedir, 'instant-node-238517-firebase-adminsdk-tiqdt-a7fbecd401.json')
os.environ["GOOGLE_APPLICATION_CREDENTIALS"]= keyfilepath
app.config["GCLOUD_PROJECT"] = "My First Project"

# app.config['SQLALCHEMY_DATABASE_URI'] =\
#         'sqlite:///' + os.path.join(basedir, 'database.db')
# app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db=SQLAlchemy(app)

cred = credentials.Certificate(keyfilepath)

firebase_admin.initialize_app(cred)





# sddlllfffff
# [END cloud_sql_mysql_sqlalchemy_create]
# auth = FirebaseAuth(app)

login_manager = LoginManager(app)
login_manager.login_view = 'sign'

class Account(UserMixin, db.Model):

    __tablename__ = 'accounts'

    account_id = db.Column(db.Integer)
    firebase_user_id = db.Column(db.String(40), unique=True, primary_key=True)
    email = db.Column(db.String(75), unique=True, nullable=False)
    email_verified = db.Column(db.Boolean, default=False, nullable=False)
    name = db.Column(db.Text)
    photo_url = db.Column(db.Text)
    
    def get_id(self):
        return self.firebase_user_id

    def __repr__(self):
        return str(dict(firebase_user_id=self.firebase_user_id, email=self.email, name=self.name))
class userField(db.Model):
    __tablename__ = 'usersFields'
    fieldid = db.Column(db.Integer, primary_key=True, autoincrement=True)
    userid = db.Column(db.Text, nullable=False)
    fieldName = db.Column(db.String(50), nullable=False)
    fieldCoordinates = db.Column(db.String(500), nullable=False)


    def __repr__(self):
        return f'<user {str(self.userid)}>', f'<fieldname {str(self.fieldName)}>', f'<fieldCoords {str(self.fieldCoordinates)}>', f'<fieldid {str(self.fieldid)}>'


# def model_exists(model_class):
#     engine = db.get_engine()
#     return model_class.metadata.tables[model_class.__tablename__].exists(engine)

# with app.app_context():
#     if not model_exists(Account) and model_exists(userField):
#         db.create_all() # <-- don't use this in production!
#         db.session.commit()
with app.app_context():
    db.create_all() # <-- don't use this in production!
    db.session.commit()

polygon_corrected=[]

def production_sign_in(token,uid):
    account = Account.query.filter_by(firebase_user_id=uid).one_or_none()
    if account is None:
        account = Account(firebase_user_id=uid)
        db.session.add(account)
    account.email = token['email']
    account.email_verified = token['email_verified']
    account.name = token.get('name')
    account.photo_url = token.get('picture')
    db.session.flush()
    login_user(account)
    db.session.commit()



# def development_sign_in(email):
#     login_user(Account.query.filter_by(email=email).one())

@app.route('/log_out', methods=['GET', 'POST'])
@login_required
def sign_out():
    logout_user()
    return redirect(url_for('/'))

@login_manager.user_loader
def load_user(firebase_user_id):
    return Account.query.get(str(firebase_user_id))


def authentication_required():
    return redirect(url_for('/signin'))# @app.route("/")


@app.after_request
def add_header(r):
    """
    Add headers to both force latest IE rendering engine or Chrome Frame,
    and also to cache the rendered page for 10 minutes.
    """
    r.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    r.headers["Pragma"] = "no-cache"
    r.headers["Expires"] = "0"
    r.headers['Cache-Control'] = 'public, max-age=0'
    return r

@app.route('/tok', methods=['POST'])
def token():
    tok = request.get_json(force=True)
    decoded_token = auth.verify_id_token(tok['idToken'])
    uid = decoded_token['uid']
    production_sign_in(decoded_token,uid)
    return json.dumps({'success':True}), 200, {'ContentType':'application/json'}



polygon = None                                                  #methods=['GET', 'POST'] enables the script to retrieve and send data

@app.route('/', methods=['GET', 'POST'])
def home():
    return render_template("index.html")


@app.route('/signin', methods=['GET', 'POST'])
def sign():
    return render_template("sign.html")


@app.route('/map', methods=['GET', 'POST'])                                         #this and the function def map() renders the test.html file in templates folder
@login_required
def map():
    #query database for user's fields
    fieldsStr = userField.query.filter_by(userid=current_user.firebase_user_id).all()
    fields = []
    centres=[]
    fieldsinStr=[]
    fieldnames=[]
    fieldids=[]
    if fieldsStr:
        for field in fieldsStr:
            feld = []
            fieldid = field.fieldid
            fieldids.append(fieldid)
            fieldname = field.fieldName
            fieldnames.append(fieldname)
            fieldCoorddStrOG = field.fieldCoordinates
            fieldsinStr.append(fieldCoorddStrOG)
            fieldCoorddStr = fieldCoorddStrOG.replace("[", "")
            fieldCoorddStr = fieldCoorddStr.replace("]", "")
            fieldCoorddStr = fieldCoorddStr.replace(" ", "")
            fieldCoorddStr = fieldCoorddStr.split(",")
            point = {}
            i = 0
            for coord in fieldCoorddStr:
                if i % 2 == 0:
                    point["lat"] = float(coord)
                else:
                    point["lng"] = float(coord)
                    feld.append(point)
                i += 1
            fields.append(feld)
            centre = {}
            centre["lat"] = sum([p["lat"] for p in feld])/len(feld)
            centre["lng"] = sum([p["lng"] for p in feld])/len(feld)
            centres.append(centre)
        client = storage.Client()  # Implicit environ set-up
        bucket_name = 'instant-node-238517.appspot.com'
        bucket = client.bucket(bucket_name)       
            
    userid=current_user.get_id()
    return render_template("change.html", fieldsStr=fieldsinStr, centres=centres,user=current_user.name,fieldnames=fieldnames,fieldids=fieldids,userid=str(userid)) #pass fields to template


@app.route('/deletefield', methods=['GET', 'POST'])
@login_required
def deletefield():

    if request.method == 'POST':
        print('Incoming..')
        req = request.get_json(force=True)
        fieldid = req["fieldid"]
        print('fieldid',fieldid)
        field = userField.query.filter_by(fieldid=fieldid).first()
        db.session.delete(field)
        db.session.commit()
        userid = current_user.get_id()
        userfieldpth = url_for('static', filename=str(userid) +'/'+ str(fieldid))
        userfieldpthOS= os.path.join(basedir, 'static', str(userid), str(fieldid))
        if os.path.exists(userfieldpthOS):
            shutil.rmtree(userfieldpthOS)
        
    return render_template("change.html")

@app.route('/editfieldname', methods=['GET', 'POST'])
@login_required
def editfieldname():
        
        if request.method == 'POST':
            print('Incoming..')
            req = request.get_json(force=True)
            fieldid = req["fieldid"]
            fieldname = req["newname"]
            print(fieldid)
            field = userField.query.filter_by(fieldid=fieldid).first()
            field.fieldName = fieldname
            db.session.commit()
            print("edited")
        return render_template("change.html")

@app.route('/editfieldcoords', methods=['GET', 'POST'])
@login_required
def editfieldcoords():
            
            if request.method == 'POST':
                print('Incoming..')
                req = request.get_json(force=True)
                fieldid = req["fieldid"]
                fieldcoords = req["geojson"]["geometry"]["coordinates"][0]
                print(fieldid)
                field = userField.query.filter_by(fieldid=fieldid).first()
                field.fieldCoordinates = json.dumps(fieldcoords)
                db.session.commit()
                print("edited")
            return render_template("change.html")

# def move_files_in_folder_to_cloud_storage(bucket_name, src_dir,dest_dir):
#         """Upload files in a local folder to a Google Cloud Storage bucket."""
#         storage_client = storage.Client()
#         bucket = storage_client.get_bucket(bucket_name)
        
#         for filename in os.listdir(src_dir):
#             file_pth = os.path.join(src_dir, filename)
#             if(not(storage.Blob(bucket=bucket, name=os.path.join(dest_dir,filename)).exists())):
#                 blob = bucket.blob(dest_dir+'/'+filename)
#                 blob.upload_from_filename(file_pth)
#             # print("File {} uploaded to {}.".format(filename, bucket_name))
#         shutil.rmtree(src_dir)

@app.route('/addfield', methods=['GET', 'POST'])                  #this and the function def result() renders the resultnew.html file in templates folder
@login_required
def addfield():

    if request.method == 'POST':
        print('Incoming..')
        req = request.get_json(force=True)
        #a = json.loads(req)
        global polygon
        polygon = req["newfield"]["geojson"]["geometry"]["coordinates"][0] # parse as JSON
        newfieldname = req["newfield"]["name"]
        m = StaticMap(100, 100, 10, 10, 'https://www.google.cn/maps/vt?lyrs=s@189&gl=cn&x={x}&y={y}&z={z}')
        fieldpoly = Polygon(polygon, '#ff0000cc', '#ff0000c9')
        m.add_polygon(fieldpoly) 
        image=m.render()

        # bucket_name = 'instant-node-238517.appspot.com'
        userid = current_user.get_id()
        

        # polygon = polygons_and_name["newfield"]["geojson"]["geometry"]["coordinates"][0]
        global polygon_corrected
        polygon_corrected= polygon.copy()
        for i in range(len(polygon_corrected)):
    #     print(i)
            for j in range(len(polygon_corrected[i])):
        #             print('j',j)
                    
                    polygon_corrected[i][j],polygon_corrected[i][1]= polygon_corrected[i][1], polygon_corrected[i][j]
        print("polygon-corr",polygon_corrected)
        print("polygon",polygon)
        field = userField(userid=current_user.firebase_user_id, fieldName=newfieldname, fieldCoordinates=str(polygon_corrected))
        db.session.add(field)
        db.session.commit()
        print("added")
        fid = field.fieldid
        userid = current_user.firebase_user_id
        # userfieldpth = basedir+'/tmp/'+ str(userid) +'/'+ str(fid)
        userfieldpth = url_for('static', filename=str(userid) +'/'+ str(fid))
        userfieldpth = userfieldpth.replace("/static", "static")
        userfieldpthOS= os.path.join(basedir, 'static', str(userid), str(fid))
        if not os.path.exists(userfieldpthOS):
            os.makedirs(userfieldpthOS)
        image.save(userfieldpth + '/thumb.png')
        
        
        print("id",id)
        print("polygon",polygon)
        res= make_response(json.dumps({"id": id}),200)

    return res

# selfield2 = '90'

@app.route('/result', methods=['POST','GET'])                  #this and the function def result() renders the resultnew.html file in templates folder
@login_required
def result():
    if request.method == 'POST':
        selfield1 = request.form.get("selected_fid")
    elif request.method == 'GET':
        selfield1 = request.args.get("selected_fid")
    # global selfield2
    # selfield2 = selfield1

    return render_template("results.html", fieldid=selfield1) 



@app.route('/code', methods=['POST','GET'])
@login_required
def code():
    # if request.method == 'POST':
    #     selfield= request.form.get("sel")
    # elif request.method == 'GET':
    #     selfield= request.args.get("sel")
    pathvi=[]
    pathmi=[]
    pathre=[]
    pathms=[]
    arrayvi=[]
    arraymi=[]
    arrayre=[]
    arrayms=[]
    
    # global polygon
    # global selfield2
    # selfield= selfield2
    # selfield_type= type(selfield)
    # selfield_conv= int(selfield)
    # selfield_conv_type= type(selfield_conv)
    # credentials = compute_engine.Credentials(scopes=['https://www.googleapis.com/auth/earthengine'])
    ee.Initialize()
    

    # dt = datetime.date(2022, 4, 1)  # add the starting date according to your satellite, year, month, day
    # q = dt.strftime("%Y-%m-%d")
    # w = q
    # from datetime import date
    # from dateutil.rrule import rrule,MONTHLY
    import datetime

    startdate= request.form.get('startdate')
    enddate= request.form.get('enddate')
    selected_fieldid= request.form.get('sel')

    fields = userField.query.filter_by(userid=current_user.firebase_user_id, fieldid=selected_fieldid).first()
    userid = current_user.firebase_user_id
    userfieldpth = url_for('static', filename=str(userid) +'/'+ str(fields.fieldid))
    userfieldpth = userfieldpth.replace("/static", "static")
    userfieldpthOS= os.path.join(basedir, 'static', str(userid), str(fields.fieldid))

    if not os.path.exists(os.path.join(userfieldpthOS,"ndvi")):
        os.makedirs(os.path.join(userfieldpthOS,"ndvi"))
    if not os.path.exists(os.path.join(userfieldpthOS,"ndmi")):
        os.makedirs(os.path.join(userfieldpthOS,"ndmi"))
    if not os.path.exists(os.path.join(userfieldpthOS,"ndre")):
        os.makedirs(os.path.join(userfieldpthOS,"ndre"))
    if not os.path.exists(os.path.join(userfieldpthOS,"msavi")):
        os.makedirs(os.path.join(userfieldpthOS,"msavi"))

    with open(userfieldpth + '/ndvi/ndvi.csv', mode='w+') as csvfile:
        csvfile.truncate(0)
    with open(userfieldpth +'/ndmi/ndmi.csv', mode='w+') as csvfile:
        csvfile.truncate(0)
    with open(userfieldpth +'/ndre/ndre.csv', mode='w+') as csvfile:
        csvfile.truncate(0)
    with open(userfieldpth +'/msavi/msavi.csv', mode='w+') as csvfile:
        csvfile.truncate(0)
    # for field in fields:
    #     if field.fieldid == int(selfield):
    #         selectedfieldid = field.fieldid
    #         break
    field=fields
    # selfield_id=field.fieldid
    # selfield_id_type= type(selfield_id)
    # selfield_id_conv= int(selfield_id)
    # selfield_id_conv_type= type(selfield_id_conv)
    fieldCoords = field.fieldCoordinates
    fieldCoords = list(eval(fieldCoords))
    # fieldCoordscopy = fieldCoords.copy()
    print("fieldCoords",fieldCoords)

    # polygon_ee=polygon.copy()
    for ring in fieldCoords:
        ring.reverse()
   
# print("polygon-ee",polygon_ee)
    print("fieldCoords",fieldCoords)

    area = ee.Geometry.Polygon([fieldCoords])
    
    total_sqkm = area.area().divide(1000 * 1000).getInfo()



    startdate=startdate.split("/")
    enddate=enddate.split("/")
    year1=int(startdate[2])
    month1=int(startdate[0])
    day1=int(startdate[1])
    year2=int(enddate[2])
    month2=int(enddate[0])
    day2=int(enddate[1])
    x= {1: 'Jan',2: 'Feb',3: 'Mar',4: 'Apr',5: 'May',6: 'Jun',7: 'Jul' ,8: 'Aug',9: 'Sep',10: 'Oct',11: 'Nov',12: 'Dec'}
    for h in x:
        if  h == int(month1):
            z= x[h]
            mon1= z
    for k in x:
        if  k == int(month2):
            z= x[k]
            mon2= z
    stdate= str(mon1) + " "+ str(day1) + ", "+ str(year1)
    endate= str(mon2) + " "+ str(day2) + ", "+ str(year2)

    start_date = datetime.date(year1,month1,day1)
    end_date = datetime.date(year2,month2,day2)

    # bucket_name = 'instant-node-238517.appspot.com'
    # userid = current_user.get_id()

    # storage_client = storage.Client()
    # prefix=userid+'/'+str(selected_fieldid)+"/"+"viplot/"

    # Note: Client.list_blobs requires at least package version 1.17.0.
    # fieldfilescloud = storage_client.list_blobs(bucket_name, prefix=prefix, delimiter=None)

    dt = datetime.date(year1,month1,day1)  # add the starting date according to your satellite, year, month, day
    q = dt.strftime("%Y-%m-%d")
    # dt = datetime.date(2021, 5,17)  # add the starting date according to your satellite, year, month, day
    w = q
    delta = datetime.timedelta(days=5)
    a = 1
    # while a < 10:
    while (start_date < end_date): 
     
        df = dt + datetime.timedelta(days=a * 5)  # set number of days or weeks you want to extract
        q = w
        w = df.strftime("%Y-%m-%d")
        #print(w)
     
        start_date += delta
    # Define the area
      


    # Note: The call returns a response only when the iterator is consumed.
        # q_time = datetime.datetime.strptime(q, "%Y-%m-%d")
        # neighbouring_dates=[]
        # for n in range(-5,5):
        #     neighbouring_date=q_time + datetime.timedelta(days=n)
        #     neighbouring_date=neighbouring_date.strftime("%Y-%m-%d")
        #     neighbouring_dates.append(prefix+neighbouring_date+".png")
        # match = [d for d in fieldfilescloud if d in neighbouring_dates]
        # if not match:

    # define the image
        # Define the area
        area = ee.Geometry.Polygon([fieldCoords])
        # define the image
        print(q , w)

        #coll = ee.ImageCollection("LANDSAT/LC08/C01/T1_SR").filterDate("" + q + "", "" + w + "")
        
        coll = ee.ImageCollection("COPERNICUS/S2_SR").filterDate("" + q + "", "" + w + "")
    #coll = ee.ImageCollection("LANDSAT/LC08/C01/T1_SR")

        image_area = coll.filterBounds(area)
        img = image_area.median()

        '''first three bands map to R, G, B, respectively, and stretched to [0, 1] 
        since the bands are float data type. This means that the 
        coastal aerosol band ('B1') is rendered in red, the blue band ('B2') is rendered in green, 
        and the green band ('B3') is rendered in blue. To render the image as a true-color composite, 
        you need to tell Earth Engine to use the Landsat 8 bands 'B4', 'B3', and 'B2' for R, G, and B, respectively.
        source: https://developers.google.com/earth-engine/tutorials/tutorial_api_04'''

        bands = ["B4", "B3", "B2"]
        band_outputs = {}
        #red
        for band in bands:
            try:
                image = img.select(band).rename(["temp"])
            except ee.ee_exception.EEException:
                
                continue


            latlon = ee.Image.pixelLonLat().addBands(image)     #Creates an image with two bands named 'longitude' and 'latitude', containing the longitude and latitude at each pixel, in degrees.

            latlon = latlon.reduceRegion(                       #Apply a reducer to all the pixels in a specific region.
                reducer=ee.Reducer.toList(),
                geometry=area,
                maxPixels=1e8,
                scale=2)

            data = np.array((ee.Array(latlon.get("temp")).getInfo()))       #getting an array of pixel data
            lats = np.array((ee.Array(latlon.get("latitude")).getInfo()))   #getting an array of lat data
            lons = np.array((ee.Array(latlon.get("longitude")).getInfo())) 
            # print( data)
            # print(lats) #getting an array of lon data
            # print(lons)

            #get the unique coordinates
            uniqueLats = np.unique(lats)
            # print(uniqueLats)
            uniqueLons = np.unique(lons)
            # print(uniqueLons)

            #get number of columns and rows from coordinates
            ncols = len(uniqueLons)
            # print( ncols)
            nrows = len(uniqueLats)
            # print(nrows)

            #determine pixelsizes
            ys = uniqueLats[1] - uniqueLats[0]
            # print(  ys)
            xs = uniqueLons[1] - uniqueLons[0]
            # print(xs)

            #create an array with dimensions of image
            arr = np.zeros([nrows, ncols], np.float32)  # -9999
            
            # fill the array with values
            counter = 0
            for y in range(0, len(arr), 1):
                for x in range(0, len(arr[0]), 1):
                    if lats[counter] == uniqueLats[y] and lons[counter] == uniqueLons[x] and counter < len(lats) - 1:
                        arr[len(uniqueLats) - 1 - y, x] = data[counter]  # we start from lower left corner
                        counter += 1
            band_outputs[band] = arr
            # print(arr)
        if not band_outputs:
            print("No valid bands found for this image date")
    # do something else or skip this image date

        else: 
            r = np.expand_dims(band_outputs["B4"], -1).astype("float32")            #expanding the array
        g = np.expand_dims(band_outputs["B3"], -1).astype("float32")
        b = np.expand_dims(band_outputs["B2"], -1).astype("float32")
        rgb = np.concatenate((r, g, b), axis=2) / 3000                          #joining r,g,b arrays into one array called rgb

        coll = ee.ImageCollection("COPERNICUS/S2_SR").filterDate("" + q + "", "" + w + "")
        image_area = coll.filterBounds(area)
        # print("image_area", image_area)
        img = image_area.median()
        # print("img", img)



    
        RED = img.select("B4")                                                  #taking the red band
        NIR = img.select("B8")   
        SWIR = img.select("B11")  
        Rededge = img.select("B5") 
        

        
        
        NDVI = ee.Image(NIR.subtract(RED).divide(NIR.add(RED)))   #taking the near infrared band
        NDMI = ee.Image(NIR.subtract(SWIR).divide(NIR.add(SWIR)))  
        NDRE = ee.Image(NIR.subtract(Rededge).divide(NIR.add(Rededge)))  
        # MSAVI = ee.Image((2 * NIR + 1 - sqrt(pow((2 * NIR + 1), 2) - 8 * (NIR - RED)) ) / 2)
        MSAVI =ee.Image(NIR.multiply(2).add(1).subtract(NIR.multiply(2).add(1).pow(2).subtract(NIR.subtract(RED).multiply(8)).sqrt()).divide(2))
        # print("NDVI", NDVI)           #making NVDI image
        #get the lat lon and add the ndvi
        latlonvi = ee.Image.pixelLonLat().addBands(NDVI)
        latlonmi = ee.Image.pixelLonLat().addBands(NDMI)
        latlonre = ee.Image.pixelLonLat().addBands(NDRE)
        latlonms= ee.Image.pixelLonLat().addBands(MSAVI)
        # print(" latlon", latlon)
        #apply reducer to list
        latlonvi = latlonvi.reduceRegion(
            reducer=ee.Reducer.toList(),
            geometry=area,
            maxPixels=1e8,
            scale=2)
        latlonmi = latlonmi.reduceRegion(
            reducer=ee.Reducer.toList(),
            geometry=area,
            maxPixels=1e8,
            scale=2)
        latlonre = latlonre.reduceRegion(
            reducer=ee.Reducer.toList(),
            geometry=area,
            maxPixels=1e8,
            scale=2)
        latlonms = latlonms.reduceRegion(
            reducer=ee.Reducer.toList(),
            geometry=area,
            maxPixels=1e8,
            scale=2)
        datavi = np.array((ee.Array(latlonvi.get("B8")).getInfo()))                 #getting an array of pixel data from near infrared band
        latsvi = np.array((ee.Array(latlonvi.get("latitude")).getInfo()))           #getting an array of lat data
        lonsvi = np.array((ee.Array(latlonvi.get("longitude")).getInfo()))     
        print("NDVI")
        # print( "data", datavi)
        # print("lats",latsvi) 
        # print("lons",lonsvi)    
        # print("data.shape",datavi.shape)
        #get the unique coordinates
        uniqueLatsvi = np.unique(latsvi)
        uniqueLonsvi = np.unique(lonsvi)
        # print(uniqueLatsvi)
        # print(uniqueLonsvi)
        #get number of columns and rows from coordinates
        ncolsvi = len(uniqueLonsvi)
        print(ncolsvi)
        nrowsvi = len(uniqueLatsvi)
        print(nrowsvi)
        #determine pixelsizes
        ysvi = uniqueLatsvi[1] - uniqueLatsvi[0]
        xsvi = uniqueLonsvi[1] - uniqueLonsvi[0]

        #create an array with dimensions of image
        arrvi = np.empty([nrowsvi, ncolsvi], np.float32)  # -9999
        arrvi[:] = np.nan
        # print(len(arr))
        #fill the array with values
        counter = 0
        for y in range(0, len(arrvi), 1):
            for x in range(0, len(arrvi[0]), 1):
                # print("len(arr[0])",len(arr[0]))
                if latsvi[counter] == uniqueLatsvi[y] and lonsvi[counter] == uniqueLonsvi[x] and counter < len(latsvi) - 1:
                    # print(len(uniqueLats) - 1 - y, x)
                    arrvi[len(uniqueLatsvi) - 1 - y, x] = datavi[counter]  #we start from lower left corner
                    counter += 1


        #MASKING
        # import json
        ndvi = arrvi.copy()
        arrayvin=ndvi.tolist()
        # ndvis = arr.copy()
        # print('arr =',arr)
        import json
        # arrayvin = json.dumps(ndvi.tolist())  
        arrayvi.append(arrayvin)
        # print(arrayvi)
    

################# NDMI ###############################
        datami = np.array((ee.Array(latlonmi.get("B8")).getInfo()))                 #getting an array of pixel data from near infrared band
        latsmi = np.array((ee.Array(latlonmi.get("latitude")).getInfo()))           #getting an array of lat data
        lonsmi = np.array((ee.Array(latlonmi.get("longitude")).getInfo()))     
        print("NDMI")
        # print( "data", datami)
        # print("lats",latsmi) 
        # print("lons",lonsmi)    
        # print("data.shape",datami.shape)
        #get the unique coordinates
        uniqueLatsmi = np.unique(latsmi)
        uniqueLonsmi = np.unique(lonsmi)
        # print(uniqueLatsmi)
        # print(uniqueLonsmi)
        

        #get number of columns and rows from coordinates
        ncolsmi = len(uniqueLonsmi)
        print(ncolsmi)
        
        nrowsmi = len(uniqueLatsmi)
        print(nrowsmi)
        

        #determine pixelsizes
        ysmi = uniqueLatsmi[1] - uniqueLatsmi[0]
        xsmi = uniqueLonsmi[1] - uniqueLonsmi[0]

        #create an array with dimensions of image
        arrmi = np.empty([nrowsmi, ncolsmi], np.float32)  # -9999
        arrmi[:] = np.nan
        # print(len(arr))
        #fill the array with values
        counter = 0
        for y in range(0, len(arrmi), 1):
            for x in range(0, len(arrmi[0]), 1):
                # print("len(arr[0])",len(arr[0]))
                if latsmi[counter] == uniqueLatsmi[y] and lonsmi[counter] == uniqueLonsmi[x] and counter < len(latsmi) - 1:
                    # print(len(uniqueLats) - 1 - y, x)
                    arrmi[len(uniqueLatsmi) - 1 - y, x] = datami[counter]  #we start from lower left corner
                    counter += 1

        #MASKING
        # import json

    
    
        # print('arr =',arr)

        ndmi = ((np.around(arrmi.copy(),decimals=1))+0.02)
        ndmis = np.around(arrmi.copy(),decimals=1)
        # ndvis = arr.copy()
        # print('arr =',arr)
        # arraymi = json.dumps(ndmis.tolist())  
    
        arraymin=ndmis.tolist() 
        arraymi.append(arraymin)
################################  NDRE  ######################################    

        datare = np.array((ee.Array(latlonre.get("B8")).getInfo()))                 #getting an array of pixel data from near infrared band
        latsre = np.array((ee.Array(latlonre.get("latitude")).getInfo()))           #getting an array of lat data
        lonsre = np.array((ee.Array(latlonre.get("longitude")).getInfo()))     
        print("NDRE")
        # print( "data", datavi)
        # print("lats",latsvi) 
        # print("lons",lonsvi)    
        # print("data.shape",datavi.shape)
        #get the unique coordinates
        uniqueLatsre = np.unique(latsre)
        uniqueLonsre = np.unique(lonsre)
        # print(uniqueLatsvi)
        # print(uniqueLonsvi)
        

        #get number of columns and rows from coordinates
        ncolsre = len(uniqueLonsre)
        print(ncolsre)
        
        nrowsre = len(uniqueLatsre)
        print(nrowsre)
        

        #determine pixelsizes
        ysvi = uniqueLatsre[1] - uniqueLatsre[0]
        xsvi = uniqueLonsre[1] - uniqueLonsre[0]

        #create an array with dimensions of image
        arrre = np.empty([nrowsre, ncolsre], np.float32)  # -9999
        arrre[:] = np.nan
        # print(len(arr))
        #fill the array with values
        counter = 0
        for y in range(0, len(arrre), 1):
            for x in range(0, len(arrre[0]), 1):
                # print("len(arr[0])",len(arr[0]))
                if latsre[counter] == uniqueLatsre[y] and lonsre[counter] == uniqueLonsre[x] and counter < len(latsre) - 1:
                    # print(len(uniqueLats) - 1 - y, x)
                    arrre[len(uniqueLatsre) - 1 - y, x] = datare[counter]  #we start from lower left corner
                    counter += 1

        #MASKING
        # import json
        ndre = arrre.copy()
        # ndvis = arr.copy()
        # print('arr =',arr)
        import json
        # arrayre = json.dumps(ndre.tolist())  
        arrayren=ndre.tolist() 
        arrayre.append(arrayren)

    ################################  MSAVI ######################################    

        datams = np.array((ee.Array(latlonms.get("B8")).getInfo()))                 #getting an array of pixel data from near infrared band
        latsms = np.array((ee.Array(latlonms.get("latitude")).getInfo()))           #getting an array of lat data
        lonsms = np.array((ee.Array(latlonms.get("longitude")).getInfo()))     
        print("MSAVI")
        # print( "data", datavi)
        # print("lats",latsvi) 
        # print("lons",lonsvi)    
        # print("data.shape",datavi.shape)
        #get the unique coordinates
        uniqueLatsms = np.unique(latsms)
        uniqueLonsms = np.unique(lonsms)
        # print(uniqueLatsvi)
        # print(uniqueLonsvi)
        

        #get number of columns and rows from coordinates
        ncolsms = len(uniqueLonsms)
        print(ncolsms)
        
        nrowsms = len(uniqueLatsms)
        print(nrowsms)
        

        #determine pixelsizes
        ysms = uniqueLatsms[1] - uniqueLatsms[0]
        xsms = uniqueLonsms[1] - uniqueLonsms[0]

        #create an array with dimensions of image
        arrms = np.empty([nrowsms, ncolsms], np.float32)  # -9999
        arrms[:] = np.nan
        # print(len(arr))
        #fill the array with values
        counter = 0
        for y in range(0, len(arrms), 1):
            for x in range(0, len(arrms[0]), 1):
                # print("len(arr[0])",len(arr[0]))
                if latsms[counter] == uniqueLatsms[y] and lonsms[counter] == uniqueLonsms[x] and counter < len(latsms) - 1:
                    # print(len(uniqueLats) - 1 - y, x)
                    arrms[len(uniqueLatsms) - 1 - y, x] = datams[counter]  #we start from lower left corner
                    counter += 1

        #MASKING
        # import json
        msavi= arrms.copy()
        # ndvis = arr.copy()
        # print('arr =',arr)
        import json
        # arrayms = json.dumps(msavi.tolist())    
        arraymsn=msavi.tolist() 
        arrayms.append(arraymsn)
###############################################################
        np.savetxt(userfieldpth +"/ndvi/ndvi-arr.csv", ndvi, delimiter=",")
        np.savetxt(userfieldpth +"/ndmi/ndmi-arr.csv", ndmi, delimiter=",")
        np.savetxt(userfieldpth +"/ndre/ndre-arr.csv", ndre, delimiter=",")
        np.savetxt(userfieldpth +"/msavi/msavi-arr.csv", msavi, delimiter=",")
    
        print("ndvi")
        print("ndvi.shape", ndvi.shape)
        # print("max", np.max(ndvi))
        maxvi =np.nanmax(ndvi)
        minvi = np.nanmin(ndvi)
        avgvi= np.nanmean(ndvi)
        print("max", maxvi)
        print("min", minvi)
        print("average", avgvi)

        print("ndmi")
        print("ndmi.shape", ndmi.shape)
        # print("max", np.max(ndvi))
        maxmi =np.nanmax(ndmi)
        minmi = np.nanmin(ndmi)
        avgmi= np.nanmean(ndmi)
        print("max", maxmi)
        print("min", minmi)
        print("average", avgmi)

        print("ndre")
        print("ndre.shape", ndre.shape)
        # print("max", np.max(ndvi))
        maxre =np.nanmax(ndre)
        minre = np.nanmin(ndre)
        avgre= np.nanmean(ndre)
        print("max", maxre)
        print("min", minre)
        print("average", avgre)

        print("msavi")
        print("msavi.shape", msavi.shape)
        # print("max", np.max(ndvi))
        maxms =np.nanmax(msavi)
        minms = np.nanmin(msavi)
        avgms= np.nanmean(msavi)
        print("max", maxms)
        print("min", minms)
        print("average", avgms)
        # print("mean", np.mean(ndvi))
        # print ("min value element : ", my_data.min(axis=0)[1])
        # print ("max value element : ", my_data.max(axis=0)[2])
        # minVal, maxVal = [], []
        # for i in data:
        #     minVal.append(i[1])
        #     maxVal.append(i[2])


        # print min(minVal)
        # print max(maxVal)
        outputmi = rgb.copy()
        # output[:, :, 0] = blue
        # output[:, :, 2] = red
        outputmi *= 255
        outputmi = cv2.cvtColor(outputmi, cv2.COLOR_BGR2RGB)
        # cv2.imwrite("/tmp/ndmi/{}.jpg".format(a), outputmi)


        outputre = rgb.copy()
        # output[:, :, 0] = blue
        # output[:, :, 2] = red
        outputre *= 255
        outputre = cv2.cvtColor(outputre, cv2.COLOR_BGR2RGB)
        # cv2.imwrite("/tmp/ndre/{}.jpg".format(a), outputre)

        outputms = rgb.copy()
        # output[:, :, 0] = blue
        # output[:, :, 2] = red
        outputms *= 255
        outputms = cv2.cvtColor(outputms, cv2.COLOR_BGR2RGB)
        # cv2.imwrite("/tmp/msavi/{}.jpg".format(a), outputms)

        ndvi[ndvi < 0.4] = 0
        ndvi[ndvi > 0.4] = 1
        # with np.printoptions(threshold=np.inf):
    
        #     print("ndvi array =", ndvi)
            
        np.savetxt(basedir+"/tmp/final-ndvi.csv", ndvi, delimiter=",")
        # file = "final-ndvi.csv"
        ndvi[ndvi >= 0.5] = 0
        blue = rgb[:, :, 0]
        red = rgb[:, :, 2]
        blue[ndvi == 1] -= 0.5
        red[ndvi == 1] -= 0.5
        outputvi = rgb.copy()
        outputvi[:, :, 0] = blue
        outputvi[:, :, 2] = red
        outputvi *= 255
        outputvi = cv2.cvtColor(outputvi, cv2.COLOR_BGR2RGB)

    
    

        #cv2.imwrite("/Users/admin/PycharmProjects/greenarea/static/l.jpg", output)
        #cv2.imwrite("E:/greenarea/static/l.jpg", output)
        # cv2.imwrite("/tmp/ndvi/{}.jpg".format(a), outputvi)

    
        
        cv2.waitKey(0)
        cv2.destroyAllWindows()

        # a = request.args.get('X', 0, type=int)
        # b = request.args.get('Y', 0, type=int)

        # print(a,b)hhhhhhhhhhhhhhhhhhhhhhhhhhh
        # CALCULATIONS
        total_img = np.sum(rgb, axis=-1)
        total_pixels = len(total_img[total_img != 0])
        green_pixels = len(ndvi[ndvi != 0])
        build_pixels = total_pixels - green_pixels
        percent = (green_pixels / total_pixels) * 100
        total = total_sqkm
        green = (percent / 100) * total
        nongreen = total - green
        build = total_sqkm - green
        print("percentage", percent)
        


        

        with open(userfieldpth + '/main.csv', 'w+', newline="") as f:
            thewriter = csv.writer(f)
            if a == 1:
                thewriter.writerow(['Date', 'TotalArea', 'GreenArea', 'NongreenArea', 'Percentage', 'Coordinates'])
            thewriter.writerow([w, total, green, nongreen, percent, fieldCoords])
        
        with open(userfieldpth +'/ndvi/ndvi.csv', 'a', newline="") as f:
            thewriter = csv.writer(f)
            if a == 1:
                thewriter.writerow(['date', 'min','avg','max'])
            thewriter.writerow([q,minvi,avgvi,maxvi ])
        with open(userfieldpth +'/ndmi/ndmi.csv', 'a', newline="") as f:
            thewriter = csv.writer(f)
            if a == 1:
                thewriter.writerow(['date', 'min','avg','max'])
            thewriter.writerow([q,minmi,avgmi,maxmi ])
        with open(userfieldpth + '/ndre/ndre.csv', 'a', newline="") as f:
            thewriter = csv.writer(f)
            if a == 1:
                thewriter.writerow(['date', 'min','avg','max'])
            thewriter.writerow([q,minre,avgre,maxre ])
        with open(userfieldpth +'/msavi/msavi.csv', 'a', newline="") as f:
            thewriter = csv.writer(f)
            if a == 1:
                thewriter.writerow(['date', 'min','avg','max'])
            thewriter.writerow([q,minms,avgms,maxms ])

        if not os.path.exists(os.path.join(userfieldpthOS,"ndvi","viplot")):
            os.makedirs(os.path.join(userfieldpthOS,"ndvi","viplot"))
        if not os.path.exists(os.path.join(userfieldpthOS,"ndmi","miplot")):
            os.makedirs(os.path.join(userfieldpthOS,"ndmi","miplot"))
        if not os.path.exists(os.path.join(userfieldpthOS,"ndre","replot")):
            os.makedirs(os.path.join(userfieldpthOS,"ndre","replot"))
        if not os.path.exists(os.path.join(userfieldpthOS,"msavi","msplot")):
            os.makedirs(os.path.join(userfieldpthOS,"msavi","msplot"))
        

        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        colorvi = pd.read_csv(userfieldpth+'/ndvi/ndvi-arr.csv')
        color_palettevi = sns.color_palette("RdYlGn",as_cmap=True)

        # Pass palette to plot and set axis ranges
        sns.heatmap(colorvi,
                    cmap=color_palettevi,
                    center=0.5,
                    vmin=0,
                    vmax=1,
                    yticklabels=False,
                    xticklabels=False,
                    cbar=False
                )
        plt.savefig(userfieldpth+"/ndvi/viplot/{}.png".format(q),bbox_inches='tight',pad_inches=0,transparent=True)
        # plotvi= basedir+"/tmp/viplot/{}.jpg".format(a)
        pathvi.append("/ndvi/viplot/{}.png".format(q))

        colormi = pd.read_csv(userfieldpth+'/ndmi/ndmi-arr.csv')
        for i in np.arange(0,1,0.1):
            colormi[colormi == i] = i + 0.01
        colors=["#AF998C",'#B49E95','#BAA49E','#BFAAA8','#C5B0B2','#CBB6BC','#D0BBC5', '#D6C1CF', '#CBB9D2', '#BAADD3', '#A8A0D5','#9894D6','#8788D7','#767BD8','#646ED9','#5362DA','#4356DB','#3249DC','#213DDD','#0F30DE']
        color_palettemi = sns.color_palette(colors,as_cmap=True)


        # Pass palette to plot and set axis ranges
        sns.heatmap(colormi,
                    cmap=color_palettemi,
                    center=0,
                    vmin=-1,
                    vmax=1,
                    yticklabels=False,
                    xticklabels=False,
                    cbar=False
                )
        plt.savefig(userfieldpth+"/ndmi/miplot/{}.png".format(q),bbox_inches='tight',pad_inches=0,transparent=True)
        # plotmi= basedir+"/tmp/miplot/{}.jpg".format(a)
        
        pathmi.append("/ndmi/miplot/{}.png".format(q))

        colorre = pd.read_csv(userfieldpth+'/ndre/ndre-arr.csv')
        color_palettere = sns.color_palette("RdYlGn",as_cmap=True)

        # Pass palette to plot and set axis ranges
        sns.heatmap(colorre,
                    cmap=color_palettere,
                    center=0.5,
                    vmin=0,
                    vmax=1,
                    yticklabels=False,
                    xticklabels=False,
                    cbar=False
                )
        plt.savefig(userfieldpth+"/ndre/replot/{}.png".format(q),bbox_inches='tight',pad_inches=0,transparent=True)
        # plotvi= basedir+"/tmp/viplot/{}.jpg".format(a)
        pathre.append("/ndre/replot/{}.png".format(q))

        colorms = pd.read_csv(userfieldpth+'/msavi/msavi-arr.csv')
        color_palettems = sns.color_palette("RdYlGn",as_cmap=True)

        # Pass palette to plot and set axis ranges
        sns.heatmap(colorms,
                    cmap=color_palettems,
                    center=0.5,
                    vmin=0,
                    vmax=1,
                    yticklabels=False,
                    xticklabels=False,
                    cbar=False
                )
        plt.savefig(userfieldpth+"/msavi/msplot/{}.png".format(q),bbox_inches='tight',pad_inches=0,transparent=True)
        # plotvi= basedir+"/tmp/viplot/{}.jpg".format(a)
        pathms.append("/msavi/msplot/{}.png".format(q))
        a = a + 1
    if percent < 30:
        p1 = "Plantation less than 30% is not considered as optimal so kindly plant more trees."
    else:
        p1 = "Plantation is above 30%, you can plant more if you need or help others to plant trees."
    

    
   
   
    datavi = pd.read_csv(userfieldpth+'/ndvi/ndvi.csv', on_bad_lines='skip')
    datami = pd.read_csv(userfieldpth+'/ndmi/ndmi.csv', on_bad_lines='skip')
    datare = pd.read_csv(userfieldpth+'/ndre/ndre.csv', on_bad_lines='skip')
    datams = pd.read_csv(userfieldpth+'/msavi/msavi.csv', on_bad_lines='skip')

    
    # temp_location = basedir+'/tmp/'         #here
    # bucket_name = 'instant-node-238517.appspot.com'
    
    # def cors_configuration(bucket_name):
    #     """Set a bucket's CORS policies configuration."""
    #     # bucket_name = "your-bucket-name"

    #     storage_client = storage.Client()
    #     bucket = storage_client.get_bucket(bucket_name)
    #     bucket.cors = [
    #         {
    #             "origin": ["https://instant-node-238517.appspot.com","https://instant-node-238517.ew.r.appspot.com"],
    #             "responseHeader": [
    #                 "Content-Type",
    #                 "x-goog-resumable"],
    #             "method": ['PUT', 'POST', 'GET', 'DELETE', 'OPTIONS'],
    #             "maxAgeSeconds": 3600
    #         }
    #     ]
    #     bucket.patch()

    #     # print(f"Set CORS policies for bucket {bucket.name} is {bucket.cors}")
    #     return bucket
    
    # cors_configuration(bucket_name)

    # directory = os.fsencode(directory_in_str)
    
    # directory = os.fsencode(directory_in_str)
    
    
    
    # userid = current_user.get_id()
    # move_files_in_folder_to_cloud_storage(bucket_name, temp_location+'viplot',dest_dir=userid+'/'+str(field.fieldid)+'/'+'viplot')
    # move_files_in_folder_to_cloud_storage(bucket_name, temp_location+'miplot',dest_dir=userid+'/'+str(field.fieldid)+'/'+'miplot')
    # move_files_in_folder_to_cloud_storage(bucket_name, temp_location+'replot',dest_dir=userid+'/'+str(field.fieldid)+'/'+'replot')
    # move_files_in_folder_to_cloud_storage(bucket_name, temp_location+'msplot',dest_dir=userid+'/'+str(field.fieldid)+'/'+'msplot')


    # image_url = "https://storage.googleapis.com/mybucket/" + filename

    
    # import shutil
    # folder = basedir+'/tmp'
    # for filename in os.listdir(folder):
    #     file_path = os.path.join(folder, filename)
    #     try:
    #         if os.path.isfile(file_path) or os.path.islink(file_path):

    #             os.unlink(file_path)

    #         elif os.path.isdir(file_path):

    #             shutil.rmtree(file_path)

    #     except Exception as e:

    #         print('Failed to delete %s. Reason: %s' % (file_path, e))
    

    datearray= datavi['date'].tolist()
    dates_arr = []
    for date in datearray:
        dates_arr.append(datetime.datetime.strptime(date, "%Y-%m-%d").strftime("%d %B, %Y"))
        
    # import json
    # dates_arr= json.dumps(dates_arr)
    # x= {1 + (i - 1) % 12:calendar.month_name[i] for i in range(1, 13)}
    x= {1: 'Jan',2: 'Feb',3: 'Mar',4: 'Apr',5: 'May',6: 'Jun',7: 'Jul',8: 'Aug',9: 'Sep',10: 'Oct',11: 'Nov',12: 'Dec'}

    # monvi = datavi['date'].str[-5:-3]
    # dayvi=datavi['date'].astype(str).str[-2:]
    # monmi = datami['date'].str[-5:-3]
    # daymi=datami['date'].astype(str).str[-2:]
    # k=0

    # for g in monvi:
    #     for h in x:
    #         if  h == int(float(g)):
    #             z=  x[h]
    #             datavi['date'][k] = dayvi[k] + " "+ z
    #             k=k+1
    # print(datavi)
    # k=0
    # for g in monmi:
    #     for h in x:
    #         if  h == int(float(g)):
    #             z=  x[h]
    #             datami['date'][k] = daymi[k] + " "+ z
    #             k=k+1
    # print(datami)
    # firstrow= ['date','min', 'avg','max']
    # print(data.columns.values)
    lvi=list(datavi.values.tolist())
    # lvi.insert(0, firstrow)
    import json
    dicvi= json.dumps(lvi)
    print(dicvi)
    
    lmi=list(datami.values.tolist())
    # lmi.insert(0, firstrow)
    import json
    dicmi= json.dumps(lmi)
    # print(lmi)
    lre=list(datare.values.tolist())
    # lmi.insert(0, firstrow)
    import json
    dicre= json.dumps(lre)

    lms=list(datams.values.tolist())
    # lmi.insert(0, firstrow)
    import json
    dicms= json.dumps(lms)
    # print('lre',lre)
######################################        weather data        ###############################
    from datetime import datetime
    from meteostat import Point, Daily,Hourly
    # Set time period
    start = datetime(year1,month1,day1)
    end = datetime(year2,month2,day2)
    x= {1: 'Jan',2: 'Feb',3: 'Mar',4: 'Apr',5: 'May',6: 'Jun',7: 'Jul',8: 'Aug',9: 'Sep',10: 'Oct',11: 'Nov',12: 'Dec'}
    # vancouver = Point(25.14780973,67.21414)
    vancouver = Point(lats[0],lons[0])
    # print(vancouver)  
    data1 = Daily(vancouver, start, end)
    data1 = data1.fetch()
    # print(data1)
    # data1.to_csv('weather-daily.csv')
    weather1= pd.read_csv('weather-daily.csv', on_bad_lines='skip')
    k=0
    # monthwthr1 = weather1['time'].str[-5:-3]
    # daywthr1=weather1['time']
    # for g in monthwthr1:
    #     for h in x:
    #         if  h == int(float(g)):
    #             z=  x[h]
    #             weather1['time'][k] = "new Date"+ "("+ '"'+daywthr1[k]+'"'+ ")"
    #             k=k+1

    wthr1=weather1[weather1.columns[:4]]
    ltmp=list(wthr1.values.tolist())
    # translation = {39: None}
    # ltmp=str(ltmp).translate(translation)
    # print(ltmp)
    import json
    dictmp= json.dumps(ltmp)

    # Get hourly data
    data2 = Hourly(vancouver, start, end)
    data2 = data2.fetch()
    # data2.to_csv('weather-hourly.csv')
    weather2= pd.read_csv('weather-hourly.csv', on_bad_lines='skip')
    k=0
    # monthwthr2 = weather2['time'].str[5:7]
    # daywthr2= weather2['time']
    # for g in monthwthr2:
    #     for h in x:
    #         if  h == int(float(g)):
    #             z=  x[h]
    #             weather2['time'][k] =  "new Date"+ "("+ '"'+daywthr2[k]+'"'+ ")"
    #             k=k+1

    wthr2=weather2[weather2.columns[:-8:3]]
    # print(wthr2)
    # translation = {39: None}
    lhum=list(wthr2.values.tolist())
    # lhum=str(lhum).translate(translation)
    # print(lhum)
    import json
    dichum= json.dumps(lhum)

    


 
    # print(pathvi)

    # print(pathmi)
    # print(pathre) 
    # print(arrayvi)
    # print(type(arrayvi))
    # print(type(pathvi))
    # polygonss = polygon
    # for i in range(len(polygonss)):
    # #     print(i)
    #         for j in range(len(polygonss[i])):
    #     #             print('j',j)
    #                 x=1
    #                 polygonss[i][j],polygonss[i][x]= polygonss[i][x], polygonss[i][j]
    # print(polygonss)

    # delete all files in temp folder
    
# update
    return render_template("finalnew.html",polygonss=field.fieldCoordinates,dates_arr=dates_arr,b=total, c=green, d=build, e=percent, f=p1,nrowsvi=nrowsvi,nrowsmi=nrowsmi,nrowsre=nrowsre,nrowsms=nrowsms,ncolsvi=ncolsvi, ncolsmi=ncolsmi,ncolsre=ncolsre, ncolsms=ncolsms,ndvi=simplejson.dumps(arrayvi, ignore_nan=True) ,ndmi=simplejson.dumps(arraymi, ignore_nan=True),ndre=simplejson.dumps(arrayre,ignore_nan=True),msavi=simplejson.dumps(arrayms,ignore_nan=True), pathvi=pathvi,pathmi=pathmi,pathre=pathre,pathms=pathms,dicvi=dicvi,dicmi=dicmi,dicre=dicre,dicms=dicms,dictmp=dictmp,dichum=dichum,startdate=stdate,enddate=endate,uid=str(userid),fid=str(field.fieldid))

# @app.route('/my', methods=['GET', 'POST'])
# def my():

#     import pandas as pd
#     datavi = pd.read_csv('ndvi.csv', on_bad_lines='skip')
#     datami = pd.read_csv('ndmi.csv', on_bad_lines='skip')
#     x= {1: 'Jan',2: 'Feb',3: 'Mar',4: 'Apr',5: 'May',6: 'Jun',7: 'Jul',8: 'Aug',9: 'Sep',10: 'Oct',11: 'Nov',12: 'Dec'}

#     monvi = datavi['date'].str[-5:-3]
#     dayvi=datavi['date'].astype(str).str[-2:]
#     monmi = datami['date'].str[-5:-3]
#     daymi=datami['date'].astype(str).str[-2:]
#     k=0

#     for g in monvi:
#         for h in x:
#             if  h == int(float(g)):
#                 z=  x[h]
#                 datavi['date'][k] =  dayvi[k] + " "+ z
#                 k=k+1
#     print(datavi)
#     k=0
#     for g in monmi:
#         for h in x:
#             if  h == int(float(g)):
#                 z=  x[h]
#                 datami['date'][k] =  daymi[k] + " "+ z
#                 k=k+1
#     print(datami)
#     # firstrow= ['date','min', 'avg','max']
#     # print(data.columns.values)
#     lvi=list(datavi.values.tolist())
#     # lvi.insert(0, firstrow)
#     import json
#     dicvi= json.dumps(lvi)
    
#     lmi=list(datami.values.tolist())
#     print(lmi)
#     # lmi.insert(0, firstrow)
#     import json
#     dicmi= json.dumps(lmi)
#     plotvi="/tmp/viplot/12.jpg"
#     plotmi= "/tmp/miplot/12.jpg"
#     from datetime import datetime
#     from meteostat import Point, Daily,Hourly
#     # Set time period
#     start = datetime(2022, 5, 17)
#     end = datetime(2022, 6, 9)
#     x= {1: 'Jan',2: 'Feb',3: 'Mar',4: 'Apr',5: 'May',6: 'Jun',7: 'Jul',8: 'Aug',9: 'Sep',10: 'Oct',11: 'Nov',12: 'Dec'}
#     vancouver = Point(25.14780973,67.21414)
#     # vancouver = Point(lats[0],lons[0])
#     print(vancouver)
#     data1 = Daily(vancouver, start, end)
#     data1 = data1.fetch()
#     print(data1)
#     data1.to_csv('weather-daily.csv')
#     weather1= pd.read_csv('weather-daily.csv', on_bad_lines='skip')

#     k=0
#     monthwthr1 = weather1['time'].str[-5:-3]
#     daywthr1=weather1['time']
#     for g in monthwthr1:
#         for h in x:
#             if  h == int(float(g)):
#                 z=  x[h]
#                 weather1['time'][k] = "new Date"+ "("+ '"'+daywthr1[k]+'"'+ ")"
#                 k=k+1

#     wthr1=weather1[weather1.columns[:4]]
#     ltmp=list(wthr1.values.tolist())
#     translation = {39: None}
#     ltmp=str(ltmp).translate(translation)
#     print(ltmp)
#     import json
#     dictmp= json.dumps(ltmp)

#     # Get hourly data
#     data2 = Hourly(vancouver, start, end)
#     data2 = data2.fetch()
#     data2.to_csv('weather-hourly.csv')
#     weather2= pd.read_csv('weather-hourly.csv', on_bad_lines='skip')
#     k=0
#     monthwthr2 = weather2['time'].str[5:7]
#     daywthr2= weather2['time']
#     for g in monthwthr2:
#         for h in x:
#             if  h == int(float(g)):
#                 z=  x[h]
#                 weather2['time'][k] =  "new Date"+ "("+ '"'+daywthr2[k]+'"'+ ")"
#                 k=k+1

#     wthr2=weather2[weather2.columns[:-8:3]]
#     print(wthr2)
#     translation = {39: None}
#     lhum=list(wthr2.values.tolist())
#     lhum=str(lhum).translate(translation)
#     print(lhum)
#     import json
#     dichum= json.dumps(lhum)

    
 
#     return render_template('final.html',dicvi=dicvi,dicmi=dicmi,plotvi=plotvi,plotmi=plotmi,dichum=dichum,dictmp=dictmp)
# @app.route('/dec', methods=['GET', 'POST'])
# def dec():
#     return render_template("dec.html")
if __name__ == '__main__':
    app.debug = True
    app.run()
