import pandas as pd
import numpy as np
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from sklearn.model_selection import train_test_split
from sklearn.linear_model import ElasticNet
from aivle_big.decorators import login_required
from aivle_big.exceptions import ValidationError, NotFoundError, InternalServerError, InvalidRequestError, UnauthorizedError
import json
import logging

logger = logging.getLogger(__name__)

# CSV 파일 경로
CSV_FILE_PATH = 'prediction/all_crop_data.csv'  # 수익률 예측
CSV_FILE_PATH_1 = 'prediction/predict_code.csv'  # 품목 코드
re = {'서울': ['1101', '108'], '부산': ['2100', '159'], '대구': ['2200', '143'], '광주': ['2401', '156'], '대전': ['2501', '133']}

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
    merged_df['price'] = merged_df['price'].ffill().shift(-1)
    merged_df.dropna(subset=['price'], inplace=True)
    merged_df['year'] = merged_df['tm'].dt.year
    merged_df['month'] = merged_df['tm'].dt.month
    merged_df['day'] = merged_df['tm'].dt.day
    X = merged_df.drop(['price', 'tm'], axis=1)
    y = merged_df['price']
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=1, shuffle=False)
    model = ElasticNet(alpha=0.1, l1_ratio=0.5, max_iter=10000)
    model.fit(X_train, y_train)
    target = df_2.iloc[[-1]].copy()
    target['year'] = target['tm'].dt.year
    target['month'] = target['tm'].dt.month
    target['day'] = target['tm'].dt.day
    target.drop('tm', axis=1, inplace=True)
    pred_value = int(model.predict(target))
    return pred_value

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

def save_session_data(request, total_income, crop_results):
    session_data = {
        'total_income': total_income, 
        'results': convert_values(crop_results),
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    if 'prediction_history' not in request.session:
        request.session['prediction_history'] = []
    request.session['prediction_history'].append(session_data)
    request.session.modified = True

@login_required
def predict_income(request):
    if request.method != 'POST':
        raise InvalidRequestError("Invalid request method. Only POST is allowed.", code=405)
    
    try:
        data = json.loads(request.body)
        land_area = float(data['land_area'])
        crop_names = data['crop_names']
        crop_ratios = [float(ratio) for ratio in data['crop_ratios']]
        region = data['region']

        if sum(crop_ratios) != 1:
            raise ValidationError("The sum of crop ratios must equal 1.", code=1001)

        df = read_csv_data()
        total_predicted_value = 0
        crop_results = []

        # Fetch weather data once
        df_2 = fetch_weather_data(region)
        if df_2 is None:
            raise NotFoundError("Weather data could not be found.", code=404)

        # Set weather data range
        start_date = df_2['tm'].iloc[0].strftime('%Y%m%d')
        end_date = df_2['tm'].iloc[-1].strftime('%Y%m%d')

        for crop_name, crop_ratio in zip(crop_names, crop_ratios):
            adjusted_income, adjusted_data, latest_year = fetch_crop_data(crop_name, df, land_area, crop_ratio)
            if adjusted_income is None:
                raise NotFoundError(f"Data for {crop_name} could not be found.", code=404)

            total_predicted_value += int(adjusted_income)  # Convert to int

            # Fetch market prices matching the weather data
            df_1 = fetch_market_prices(crop_name, region, start_date, end_date)
            if df_1 is None:
                raise NotFoundError(f"Market data for {crop_name} could not be found.", code=404)

            merged_df = pd.merge(df_2, df_1, on='tm', how='left')
            merged_df.drop('itemname', axis=1, inplace=True)

            # Convert merged_df to JSON format and add to results
            df_1_json = df_1.to_json(orient='records', date_format='iso')

            pred_value = int(predict_prices(merged_df, df_2))  # Convert to int
            crop_results.append({
                'crop_name': crop_name,
                'latest_year': int(latest_year),
                'adjusted_data': convert_values(adjusted_data),
                'price': int(pred_value),
                'crop_chart_data': json.loads(df_1_json)
            })

        save_session_data(request, int(total_predicted_value), crop_results)

        return JsonResponse({
            'total_income': int(total_predicted_value),
            'results': crop_results,
        }, status=200)

    except json.JSONDecodeError:
        raise ValidationError("Invalid JSON format.", code=400)
    except ValidationError as e:
        return JsonResponse({'status': 'error', 'message': str(e), 'code': e.error_code, 'status_code': e.status_code}, status=e.status_code)
    except NotFoundError as e:
        return JsonResponse({'status': 'error', 'message': str(e), 'code': e.error_code, 'status_code': e.status_code}, status=e.status_code)
    except InvalidRequestError as e:
        return JsonResponse({'status': 'error', 'message': str(e), 'code': e.error_code, 'status_code': e.status_code}, status=e.status_code)
    except InternalServerError as e:
        return JsonResponse({'status': 'error', 'message': e.message, 'code': e.error_code, 'status_code': e.status_code}, status=e.status_code)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise InternalServerError(f"An unexpected error occurred: {str(e)}")
    
@login_required
def session_history(request):
    prediction_history = request.session.get('prediction_history', [])
    return render(request, 'session_history.html', {'prediction_history': prediction_history})