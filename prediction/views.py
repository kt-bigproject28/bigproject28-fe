import pandas as pd
import numpy as np
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from sklearn.model_selection import train_test_split
from sklearn.linear_model import ElasticNet
from sklearn.metrics import r2_score, mean_squared_error
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from aivle_big.decorators import login_required
from aivle_big.exceptions import ValidationError, NotFoundError, InternalServerError, InvalidRequestError, UnauthorizedError
from .models import PredictionSession, PredictionResult
from django.db import transaction
import json
import logging
import uuid
from django.utils import timezone
from django.views.decorators.http import require_http_methods
session_id = str(uuid.uuid4())

logger = logging.getLogger(__name__)

# CSV 파일 경로
CSV_FILE_PATH = 'prediction/all_crop_data.csv'  # 수익률 예측
CSV_FILE_PATH_1 = 'prediction/predict_code.csv'  # 품목 코드
re = {'서울': ['1101', '108'], '부산': ['2100', '159'], '대구': ['2200', '143'], '광주': ['2401', '156'], '대전': ['2501', '133']}

def get_crop_names(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'Invalid request method. Only GET is allowed.'}, status=405)
    try:
        crop_df= pd.read_csv(CSV_FILE_PATH_1)
        crop_names = crop_df['품목명'].dropna().tolist()
        return JsonResponse({'crop_names': crop_names})
    except Exception as e:
        return JsonResponse({'error': f"An unexpected error occured: {str(e)}"}, status=500)

def get_region_names(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'Invalid request method. Only GET is allowed'}, status=400)
    try:
        region_names = list(re.keys())
        return JsonResponse({'region_names': region_names})
    except Exception as e:
        return JsonResponse({'error': f"An unexpected error occured: {str(e)}"}, status = 500)

def read_csv_data():
    df = pd.read_csv(CSV_FILE_PATH, encoding='utf-8')
    df['소득률 (%)'] = df['소득률 (%)'].astype(str)
    df['부가가치율 (%)'] = df['부가가치율 (%)'].astype(str)
    df['농가수취가격 (원/kg)'] = df['농가수취가격 (원/kg)'].astype(str)
    return df

def fetch_crop_data(crop_name, df, land_area, crop_ratio):
    crop_data = df[df['작물명'] == crop_name]
    if not crop_data.empty:
        latest_crop_data = crop_data.sort_values(by='시점', ascending=False).iloc[0]
        crop_income = latest_crop_data['소득 (원)']
        latest_year = latest_crop_data['시점']
        adjusted_income = (crop_income / 302.5) * land_area * crop_ratio  
        adjusted_data = latest_crop_data.copy()
        for col in adjusted_data.index:
            if pd.api.types.is_numeric_dtype(adjusted_data[col]):
                adjusted_data[col] = (adjusted_data[col] / 302.5) * land_area * crop_ratio 
        return adjusted_income, adjusted_data.to_dict(), latest_year
    else:
        return None, None, None

def fetch_market_prices(crop_name, region, start_date, end_date):
    price_code = pd.read_csv(CSV_FILE_PATH_1, encoding='utf-8')
    itemcategorycode = int(price_code.loc[price_code['품목명'] == crop_name, '부류코드'].values[0])
    itemcode = int(price_code.loc[price_code['품목명'] == crop_name, '품목코드'].values[0])
    countrycode = re[region][0]
    params = {
        'action': 'periodProductList',
        'p_productclscode': '02',
        'p_startday': start_date,
        'p_endday': end_date,
        'p_itemcategorycode': itemcategorycode,
        'p_itemcode': itemcode,
        'p_kindcode': '',
        'p_productrankcode': '',
        'p_countrycode': countrycode,
        'p_convert_kg_yn': 'Y',
        'p_cert_key': '5d554929-4444-4cf8-9c58-618f30877777',
        'p_cert_id': '4540',
        'p_returntype': 'xml'
    }
    response = requests.get('http://www.kamis.or.kr/service/price/xml.do', params=params)
    if response.status_code == 200:
        root = ET.fromstring(response.content)
        data = []
        for item in root.findall('.//item'):
            row = {
                'yyyy': item.find('yyyy').text if item.find('yyyy') is not None else None,
                'regday': item.find('regday').text if item.find('regday') is not None else None,
                'itemname': item.find('itemname').text if item.find('itemname') is not None else None,
                'kindname' : item.find('kindname').text if item.find('kindname') is not None else None,
                'price': item.find('price').text if item.find('price') is not None else None
            }
            data.append(row)
        df_1 = pd.DataFrame(data)
        df_1['regday'] = df_1['regday'].apply(lambda x: x.replace('/', '-') if x else '')
        df_1['price'] = df_1['price'].replace('-', 'NaN').str.replace(',', '').astype(float)
        df_1['tm'] = pd.to_datetime(df_1['yyyy'] + '-' + df_1['regday'])
        df_1.drop(columns=['yyyy', 'regday'], inplace=True)
        df_1.dropna(inplace=True)
        df_1 = df_1.reset_index(drop=True)
        kind_to_keep = df_1.loc[0, 'kindname']
        df_1 = df_1[df_1['kindname'] == kind_to_keep]
        df_1.drop(columns=['kindname'], inplace = True)
        logger.debug(f"Fetched market prices for {crop_name}: {df_1}")
        return df_1
    else:
        return None

def fetch_weather_data(region):
    stnIds = re[region][1]
    date_2 = datetime.now() - timedelta(1)
    date_2 = date_2.strftime("%Y%m%d")
    date_1 = datetime.now() - timedelta(1) - timedelta(365)
    date_1 = date_1.strftime("%Y%m%d")
    params = {
        'serviceKey': '1/eYLkvnjZNKzzUpbpb+/VWWmZExnS0ave8VahtkI0X3CiletYaxBgBnlvunpx8tckfsXBogJJIQJayprpZbmA==',
        'pageNo': '1',
        'numOfRows': '365',
        'dataType': 'XML',
        'dataCd': 'ASOS',
        'dateCd': 'DAY',
        'startDt': date_1,
        'endDt': date_2,
        'stnIds': stnIds
    }
    response = requests.get('http://apis.data.go.kr/1360000/AsosDalyInfoService/getWthrDataList', params=params)
    if response.status_code == 200:
        root = ET.fromstring(response.content)
        columns = ['tm', 'avgRhm', 'minTa', 'maxTa', 'maxWs', 'avgTa', 'avgWs', 'sumRn', 'ddMes']
        data = [{child.tag: child.text for child in item if child.tag in columns} for item in root.iter('item')]
        df_2 = pd.DataFrame(data, columns=columns)
        for col in columns[1:]:
            df_2[col] = pd.to_numeric(df_2[col], errors='coerce')
        df_2.fillna(0, inplace=True)
        df_2['tm'] = pd.to_datetime(df_2['tm'])
        return df_2
    else:
        return None

def predict_prices(merged_df, df_2):
    if 'price' not in merged_df:
        logger.error("Merged DataFrame does not contain 'price' column")
        raise KeyError("Merged DataFrame does not contain 'price' column")
    
    merged_df['price'] = merged_df['price'].ffill().shift(-1)
    merged_df.dropna(subset=['price'], inplace=True)
    merged_df['year'] = merged_df['tm'].dt.year
    merged_df['month'] = merged_df['tm'].dt.month
    merged_df['day'] = merged_df['tm'].dt.day
    # 추가적인 특성 엔지니어링
    merged_df['month_sin'] = np.sin(2 * np.pi * merged_df['month'] / 12)
    merged_df['month_cos'] = np.cos(2 * np.pi * merged_df['month'] / 12)
    merged_df['day_sin'] = np.sin(2 * np.pi * merged_df['day'] / 31)
    merged_df['day_cos'] = np.cos(2 * np.pi * merged_df['day'] / 31)
    for lag in range(1, 8):
        merged_df[f'price_lag_{lag}'] = merged_df['price'].shift(lag)
    merged_df['price_ma_7'] = merged_df['price'].rolling(window=7).mean()
    merged_df['price_ma_30'] = merged_df['price'].rolling(window=30).mean()
    merged_df['temp_diff'] = merged_df['maxTa'] - merged_df['minTa']
    merged_df.fillna(0, inplace=True)
    X = merged_df.drop(['price', 'tm'], axis=1)
    y = merged_df['price']
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
    model = ElasticNet(alpha=0.1, l1_ratio=0.5, max_iter=10000)
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    r2 = r2_score(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    target = X.iloc[[-1]]
    pred_value = int(model.predict(target))
    return pred_value, r2, rmse

def convert_values(data):
    if isinstance(data, dict):
        return {k: convert_values(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [convert_values(i) for i in data]
    elif isinstance(data, (np.int64, np.int32)):
        return int(data)
    elif isinstance(data, np.float64):
        return float(data)
    else:
        return data

from django.db import transaction

@login_required
@require_POST
def predict_income(request):
    logger.debug("Entered predict_income function")
    try:
        data = json.loads(request.body)
        session_id = data.get('session_id')
        session_name = data.get('session_name', 'Default Prediction Session')
        land_area = float(data['land_area'])
        
        logger.debug(f"Received data: {data}")
        
        if isinstance(data['crop_names'], list):
            crop_names = data['crop_names']
        elif isinstance(data['crop_names'], str):
            crop_names = data['crop_names'].split(',')
        else:
            logger.error("Invalid format for crop_names")
            return JsonResponse({'error': 'Invalid format for crop_names'}, status=400)

        crop_ratios = [float(ratio) for ratio in data['crop_ratios']]
        
        if not (sum(crop_ratios) == 1 or (len(crop_ratios) == 3 and crop_ratios == [0.3, 0.3, 0.3])):
            logger.error("작물 비율의 합은 1이 되어야합니다.")
            return JsonResponse({'error': '작물 비율의 합은 1이 되어야합니다.'}, status=400)

        region = data['region']
        df = read_csv_data()
        logger.debug(f"Loaded crop data: {df.head()}")
        
        df_2 = fetch_weather_data(region)
        if df_2 is None or df_2.empty:
            logger.error('날씨데이터를 불러오는 과정에서 오류가 발생했습니다.')
            return JsonResponse({'error': '날씨데이터를 불러오는 과정에서 오류가 발생했습니다.'}, status=404)
        
        total_predicted_value = 0
        crop_results = []
        r2_scores = []

        try:
            with transaction.atomic():
                prediction_session = PredictionSession.objects.create(
                    user=request.user,
                    session_id=session_id,
                    session_name=session_name,
                    crop_names=', '.join(crop_names),
                    land_area=land_area,
                    region=region,
                    total_income=0
                )
                
                start_date = df_2['tm'].iloc[0].strftime('%Y%m%d')
                end_date = df_2['tm'].iloc[-1].strftime('%Y%m%d')
            
                for crop_name, crop_ratio in zip(crop_names, crop_ratios):
                    adjusted_income, adjusted_data, latest_year = fetch_crop_data(crop_name, df, land_area, crop_ratio)
                    logger.debug(f"Fetched crop data for {crop_name}: {adjusted_income}, {latest_year}")
                    
                    if adjusted_income is None:
                        logger.error(f"No data found for {crop_name}")
                        raise ValueError(f"{crop_name}에 대한 데이터는 존재하지 않습니다.")
                    
                    total_predicted_value += int(adjusted_income)
                    
                    df_1 = fetch_market_prices(crop_name, region, start_date, end_date)
                    if df_1 is None or df_1.empty:
                        logger.error(f"No market data found for {crop_name}")
                        raise ValueError(f"{crop_name}에 대한 도매 데이터를 불러오는 과정에서 오류가 발생했습니다.")
                    
                    logger.debug(f"Market data for {crop_name}: {df_1.head()}")
                    
                    merged_df = pd.merge(df_2, df_1, on='tm', how='left')
                    logger.debug(f"Merged dataframe: {merged_df.head()}")
                    if 'price' not in merged_df:
                        logger.error(f"Missing 'price' in merged DataFrame for {crop_name}" )
                    merged_df.drop('itemname', axis=1, inplace=True)
                    
                    
                    # Ensure the predicted value is converted to native Python int type for JSON serialization
                    pred_value, r2, rmse = predict_prices(merged_df, df_2)
                    logger.debug(f"Predicted prices for {crop_name}: {pred_value}")

                    PredictionResult.objects.create(
                        session=prediction_session,
                        crop_name=crop_name,
                        predicted_income=int(adjusted_income),  # Conversion to native Python int
                        adjusted_data=convert_values(adjusted_data),
                        price=pred_value,
                        latest_year=latest_year,
                        r2_score=r2,
                        rmse=rmse
                    )
                    
                    df_1_json = df_1.to_json(orient='records', date_format='iso')
                    crop_results.append({
                        'crop_name': crop_name,
                        'latest_year': int(latest_year),
                        'adjusted_data': convert_values(adjusted_data),
                        'price': pred_value,
                        'r2_score': r2,
                        'rmse': rmse,
                        'crop_chart_data': json.loads(df_1_json)
                    })
                
                prediction_session.total_income = int(total_predicted_value)
                prediction_session.save()
            
        except ValueError as ve:
            logger.error(f"ValueError: {ve}")
            return JsonResponse({'error': str(ve)}, status=400)
        except Exception as e:
            logger.error(f"Unexpected error: {repr(e)}, Type: {type(e)}, Args: {e.args}")
            return JsonResponse({'error': 'An unexpected error occurred'}, status=500)
        
        return JsonResponse({
            'total_income': int(total_predicted_value),
            'results': crop_results,
            'r2_scores': r2_scores
        }, status=200)

    except json.JSONDecodeError:
        logger.error("JSON decoding failed")
        return JsonResponse({'error': 'Invalid JSON format'}, status=400)
    except Exception as e:
        logger.error(f"Unexpected error: {repr(e)}, Type: {type(e)}, Args: {e.args}")
        return JsonResponse({'error': 'An unexpected error occurred'}, status=500)
    
    
@login_required
def list_prediction_sessions(request):
    try:
        sessions = PredictionSession.objects.filter(user=request.user).order_by('-created_at')
        session_list = []

        for session in sessions:
            results = session.results.all()
            session_details = {
                'session_id': session.session_id,
                'session_name': session.session_name,
                'crop_names': session.crop_names,
                'land_area': session.land_area,
                'region': session.region,
                'total_income': session.total_income,
                'created_at': timezone.localtime(session.created_at).strftime('%Y-%m-%d %H:%M'),
                'results': []
            }
            for result in results:
                session_details['results'].append({
                    'crop_name': result.crop_name,
                    'predicted_income': result.predicted_income,
                    'r2_score': result.r2_score,
                    'price': result.price,
                    'rmse': result.rmse
                })
            session_list.append(session_details)

        return JsonResponse(session_list, safe=False)

    except Exception as e:
        logger.error(f"Unexpected error in list_prediction_sessions: {repr(e)}, Type: {type(e)}, Args: {e.args}")
        return JsonResponse({'error': 'An unexpected error occurred'}, status=500)



@login_required
def prediction_session_details(request, session_id):
    try:
        session = PredictionSession.objects.get(session_id=session_id, user=request.user)
        results = session.results.all().order_by('crop_name')
        details = []

        start_date = (timezone.now() - timezone.timedelta(days=365)).strftime('%Y%m%d')
        end_date = timezone.now().strftime('%Y%m%d')

        for result in results:
            df_1 = fetch_market_prices(result.crop_name, session.region, start_date, end_date)
            if df_1 is not None and not df_1.empty:
                df_1_json = df_1.to_json(orient='records', date_format='iso')
                crop_chart_data_parsed = json.loads(df_1_json)
            else:
                crop_chart_data_parsed = []

            details.append({
                'crop_name': result.crop_name,
                'predicted_income': result.predicted_income,
                'adjusted_data': result.adjusted_data,
                'price': result.price,
                'latest_year': result.latest_year,
                'r2_score': result.r2_score,
                'rmse': result.rmse,
                'crop_chart_data': crop_chart_data_parsed
            })

        return JsonResponse({
            'session_id': session.session_id,
            'session_name': session.session_name,
            'land_area': session.land_area,
            'region': session.region,
            'total_income': session.total_income,
            'created_at': timezone.localtime(session.created_at).strftime('%Y-%m-%d %H:%M'),
            'results': details
        })
    except PredictionSession.DoesNotExist:
        return JsonResponse({'error': 'Session not found'}, status=404)
    
@login_required
def delete_prediction_session(request, session_id):
    if request.method == 'DELETE':
        try:
            session = PredictionSession.objects.get(session_id=session_id, user=request.user)
            session.delete()
            return JsonResponse({'status': 'success', 'message': 'Prediction session deleted successfully'})
        except PredictionSession.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Session not found'}, status=404)
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
def submit_prediction_view(request):
    return render(request, 'prediction.html')

@csrf_exempt
@login_required
@require_http_methods(["PATCH"])
def update_session_name(request, session_id):
    try:
        data = json.loads(request.body)
        new_session_name = data.get('session_name')

        if not new_session_name:
            raise ValidationError("New session name is required", code=400)

        session = PredictionSession.objects.get(user=request.user, session_id=session_id)
        session.session_name = new_session_name
        session.save()

        return JsonResponse({'status': 'success', 'message': 'Session name updated successfully'})
    except json.JSONDecodeError:
        raise ValidationError("Invalid JSON format", code=400)
    except ValidationError as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    except NotFoundError as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=404)
    except Exception as e:
        logger.error(f"Error updating session name: {str(e)}")
        raise InternalServerError("Failed to update session name", code=500)