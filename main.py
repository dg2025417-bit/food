import streamlit as st
import requests
import re
import plotly.graph_objects as go
from datetime import date, timedelta

st.set_page_config(page_title="급식메뉴찾기", page_icon="🍱")
st.title("🍱 급식메뉴찾기")
st.write("학교 이름을 입력하면 급식 메뉴를 찾아드려요!")

# ---------------------------
# API 인증키 불러오기
# ---------------------------
API_KEY = st.secrets.get("NEIS_API_KEY", "")

# ---------------------------
# 세션 상태 초기화
# ---------------------------
if "school_list" not in st.session_state:
    st.session_state.school_list = []
if "selected_school" not in st.session_state:
    st.session_state.selected_school = None


# ---------------------------
# 학교 검색 함수
# ---------------------------
def search_school(school_name):
    url = "https://open.neis.go.kr/hub/schoolInfo"
    params = {
        "Type": "json",
        "SCHUL_NM": school_name,
    }
    if API_KEY:
        params["KEY"] = API_KEY

    try:
        res = requests.get(url, params=params, timeout=5)
        data = res.json()
    except Exception as e:
        st.error(f"학교 검색 중 오류가 발생했어요: {e}")
        return []

    if "schoolInfo" not in data:
        return []

    try:
        rows = data["schoolInfo"][1]["row"]
    except (KeyError, IndexError):
        return []

    schools = []
    for row in rows:
        schools.append({
            "학교명": row.get("SCHUL_NM"),
            "교육청코드": row.get("ATPT_OFCDC_SC_CODE"),
            "학교코드": row.get("SD_SCHUL_CODE"),
            "지역": row.get("LCTN_SC_NM"),
        })
    return schools


# ---------------------------
# 급식 메뉴 검색 함수
# ---------------------------
def search_meal(office_code, school_code, from_date, to_date):
    url = "https://open.neis.go.kr/hub/mealServiceDietInfo"
    params = {
        "Type": "json",
        "ATPT_OFCDC_SC_CODE": office_code,
        "SD_SCHUL_CODE": school_code,
        "MMEAL_SC_CODE": "2",  # 중식
        "MLSV_FROM_YMD": from_date,
        "MLSV_TO_YMD": to_date,
    }
    if API_KEY:
        params["KEY"] = API_KEY

    try:
        res = requests.get(url, params=params, timeout=5)
        data = res.json()
    except Exception as e:
        st.error(f"급식 정보를 불러오는 중 오류가 발생했어요: {e}")
        return []

    if "mealServiceDietInfo" not in data:
        return []

    try:
        rows = data["mealServiceDietInfo"][1]["row"]
    except (KeyError, IndexError):
        return []

    meals = []
    for row in rows:
        raw_menu = row.get("DDISH_NM", "")
        menu_items = raw_menu.split("<br/>")
        clean_items = [re.sub(r"\([\d.]+\)", "", item).strip() for item in menu_items]

        # 칼로리 문자열에서 숫자만 추출 (예: "651.5 Kcal" -> 651.5)
        cal_raw = row.get("CAL_INFO", "")
        cal_match = re.search(r"[\d.]+", cal_raw)
        cal_value = float(cal_match.group()) if cal_match else None

        meals.append({
            "날짜": row.get("MLSV_YMD"),
            "메뉴": clean_items,
            "칼로리": cal_raw,
            "칼로리_숫자": cal_value,
        })
    return meals


# ---------------------------
# 1단계: 학교 검색
# ---------------------------
st.subheader("1️⃣ 학교 검색")

school_input = st.text_input("학교 이름을 입력하세요 (일부만 입력해도 돼요)", placeholder="예: 당곡")

if st.button("학교 검색하기"):
    if school_input.strip() == "":
        st.warning("학교 이름을 입력해주세요.")
    else:
        with st.spinner("학교를 검색하고 있어요..."):
            result = search_school(school_input.strip())

        if not result:
            st.error("검색된 학교가 없어요. 학교 이름을 다시 확인해주세요.")
            st.session_state.school_list = []
        else:
            st.session_state.school_list = result
            st.success(f"{len(result)}개의 학교를 찾았어요!")

# ---------------------------
# 2단계: 학교 선택
# ---------------------------
if st.session_state.school_list:
    st.subheader("2️⃣ 학교 선택")

    options = [
        f"{s['학교명']} ({s['지역']})" for s in st.session_state.school_list
    ]
    selected_idx = st.selectbox("찾은 학교 중에서 선택하세요", range(len(options)), format_func=lambda i: options[i])
    st.session_state.selected_school = st.session_state.school_list[selected_idx]

# ---------------------------
# 3단계: 날짜 선택 및 급식 조회
# ---------------------------
if st.session_state.selected_school:
    st.subheader("3️⃣ 급식 조회 기간 선택")

    school = st.session_state.selected_school
    st.info(f"선택한 학교: **{school['학교명']}** ({school['지역']})")

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("조회 시작일", value=date.today())
    with col2:
        end_date = st.date_input("조회 종료일", value=date.today() + timedelta(days=6))

    if st.button("급식 메뉴 조회하기"):
        if start_date > end_date:
            st.warning("시작일이 종료일보다 늦을 수 없어요.")
        else:
            from_ymd = start_date.strftime("%Y%m%d")
            to_ymd = end_date.strftime("%Y%m%d")

            with st.spinner("급식 정보를 불러오고 있어요..."):
                meals = search_meal(
                    school["교육청코드"],
                    school["학교코드"],
                    from_ymd,
                    to_ymd,
                )

            if not meals:
                st.warning("해당 기간에는 급식 정보가 없어요. (급식이 없는 날일 수 있어요)")
            else:
                # ---------------------------
                # 급식 메뉴 목록 출력
                # ---------------------------
                st.subheader("🍽 급식 메뉴 결과")
                for meal in meals:
                    y, m, d = meal["날짜"][:4], meal["날짜"][4:6], meal["날짜"][6:8]
                    with st.container():
                        st.markdown(f"### 📅 {y}년 {m}월 {d}일")
                        for item in meal["메뉴"]:
                            if item:
                                st.write(f"- {item}")
                        st.caption(f"칼로리: {meal['칼로리']}")
                        st.divider()

                # ---------------------------
                # 칼로리 변화 그래프 (Plotly)
                # ---------------------------
                st.subheader("📊 칼로리 변화 그래프")

                # 그래프용 데이터 준비 (날짜를 보기 좋게 변환)
                graph_dates = []
                graph_cals = []
                for meal in meals:
                    if meal["칼로리_숫자"] is not None:
                        y, m, d = meal["날짜"][:4], meal["날짜"][4:6], meal["날짜"][6:8]
                        graph_dates.append(f"{m}/{d}")
                        graph_cals.append(meal["칼로리_숫자"])

                if graph_dates:
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=graph_dates,
                        y=graph_cals,
                        mode="lines+markers+text",
                        text=[f"{c:.0f}" for c in graph_cals],
                        textposition="top center",
                        line=dict(color="royalblue", width=2),
                        marker=dict(size=8, color="royalblue"),
                        name="칼로리",
                    ))
                    fig.update_layout(
                        title="일자별 급식 칼로리 변화",
                        xaxis_title="날짜",
                        yaxis_title="칼로리 (Kcal)",
                        template="plotly_white",
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("칼로리 정보가 없어 그래프를 그릴 수 없어요.")
