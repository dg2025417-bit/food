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
        clean_items = [item for item in clean_items if item]  # 빈 문자열 제거

        # 칼로리 문자열에서 숫자만 추출 (예: "651.5 Kcal" -> 651.5)
        cal_raw = row.get("CAL_INFO", "")
        cal_match = re.search(r"[\d.]+", cal_raw)
        cal_value = float(cal_match.group()) if cal_match else None

        meals.append({
            "날짜": row.get("MLSV_YMD"),
            "메뉴": clean_items,
            "메뉴_개수": len(clean_items),
            "칼로리": cal_raw,
            "칼로리_숫자": cal_value,
        })
    return meals


def format_date(ymd):
    y, m, d = ymd[:4], ymd[4:6], ymd[6:8]
    return f"{y}년 {m}월 {d}일"


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
                    with st.container():
                        st.markdown(f"### 📅 {format_date(meal['날짜'])}")
                        for item in meal["메뉴"]:
                            st.write(f"- {item}")
                        st.caption(f"칼로리: {meal['칼로리']} · 메뉴 가짓수: {meal['메뉴_개수']}개")
                        st.divider()

                # ---------------------------
                # 특징적인 날 찾기
                # ---------------------------
                # 칼로리 정보가 있는 급식만 대상으로 함
                meals_with_cal = [m for m in meals if m["칼로리_숫자"] is not None]
                # 메뉴가 1개 이상인 급식만 대상으로 함
                meals_with_menu = [m for m in meals if m["메뉴_개수"] > 0]

                if meals_with_cal and meals_with_menu:
                    max_cal_meal = max(meals_with_cal, key=lambda m: m["칼로리_숫자"])
                    min_menu_meal = min(meals_with_menu, key=lambda m: m["메뉴_개수"])
                    max_menu_meal = max(meals_with_menu, key=lambda m: m["메뉴_개수"])

                    st.subheader("🏆 특징적인 급식 비교")

                    st.markdown("""
                    > ⚠️ 참고: NEIS API는 **잔반(음식물 쓰레기)량 데이터를 제공하지 않아요.**  
                    > 대신 갖고 있는 정보(칼로리, 메뉴 가짓수)로 비교해봤어요.
                    """)

                    col1, col2, col3 = st.columns(3)

                    with col1:
                        st.markdown("#### 🔥 칼로리 최고")
                        st.write(f"**{format_date(max_cal_meal['날짜'])}**")
                        for item in max_cal_meal["메뉴"]:
                            st.write(f"- {item}")
                        st.caption(f"칼로리: {max_cal_meal['칼로리']}")

                    with col2:
                        st.markdown("#### 📉 메뉴 최소")
                        st.write(f"**{format_date(min_menu_meal['날짜'])}**")
                        for item in min_menu_meal["메뉴"]:
                            st.write(f"- {item}")
                        st.caption(f"메뉴 가짓수: {min_menu_meal['메뉴_개수']}개")

                    with col3:
                        st.markdown("#### 📈 메뉴 최다")
                        st.write(f"**{format_date(max_menu_meal['날짜'])}**")
                        for item in max_menu_meal["메뉴"]:
                            st.write(f"- {item}")
                        st.caption(f"메뉴 가짓수: {max_menu_meal['메뉴_개수']}개")

                    # ---------------------------
                    # 비교 막대그래프 (Plotly)
                    # ---------------------------
                    st.subheader("📊 비교 그래프")

                    tab1, tab2 = st.tabs(["칼로리 비교", "메뉴 가짓수 비교"])

                    with tab1:
                        fig_cal = go.Figure()
                        fig_cal.add_trace(go.Bar(
                            x=[format_date(m["날짜"]) for m in meals_with_cal],
                            y=[m["칼로리_숫자"] for m in meals_with_cal],
                            marker_color=[
                                "crimson" if m["날짜"] == max_cal_meal["날짜"] else "royalblue"
                                for m in meals_with_cal
                            ],
                            text=[f"{m['칼로리_숫자']:.0f}" for m in meals_with_cal],
                            textposition="outside",
                        ))
                        fig_cal.update_layout(
                            title="일자별 칼로리 (빨간색 = 최고 칼로리)",
                            xaxis_title="날짜",
                            yaxis_title="칼로리 (Kcal)",
                            template="plotly_white",
                        )
                        st.plotly_chart(fig_cal, use_container_width=True)

                    with tab2:
                        fig_menu = go.Figure()
                        colors = []
                        for m in meals_with_menu:
                            if m["날짜"] == min_menu_meal["날짜"]:
                                colors.append("orange")
                            elif m["날짜"] == max_menu_meal["날짜"]:
                                colors.append("seagreen")
                            else:
                                colors.append("lightgray")

                        fig_menu.add_trace(go.Bar(
                            x=[format_date(m["날짜"]) for m in meals_with_menu],
                            y=[m["메뉴_개수"] for m in meals_with_menu],
                            marker_color=colors,
                            text=[m["메뉴_개수"] for m in meals_with_menu],
                            textposition="outside",
                        ))
                        fig_menu.update_layout(
                            title="일자별 메뉴 가짓수 (주황=최소, 초록=최다)",
                            xaxis_title="날짜",
                            yaxis_title="메뉴 가짓수 (개)",
                            template="plotly_white",
                        )
                        st.plotly_chart(fig_menu, use_container_width=True)
                else:
                    st.info("비교할 만한 급식 데이터가 충분하지 않아요.")
