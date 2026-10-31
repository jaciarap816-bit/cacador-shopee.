import streamlit as st
import requests, hashlib, time, json, math
import pandas as pd

st.set_page_config(page_title="Caçador Shopee", page_icon="🎯", layout="wide")
API_URL = "https://open-api.affiliate.shopee.com.br/graphql"
DEFAULT_APP_ID = "18316410277"

def secret(name, default=""):
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default

def api(query, variables):
    app_id = str(secret("SHOPEE_APP_ID", DEFAULT_APP_ID)).strip()
    key = str(secret("SHOPEE_SECRET", "")).strip()
    if not key:
        raise RuntimeError("Falta configurar SHOPEE_SECRET nos Secrets do Streamlit.")
    body = {"query": query, "variables": variables}
    payload = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
    ts = str(int(time.time()))
    sig = hashlib.sha256((app_id + ts + payload + key).encode()).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"SHA256 Credential={app_id}, Timestamp={ts}, Signature={sig}",
    }
    r = requests.post(API_URL, data=payload.encode("utf-8"), headers=headers, timeout=30)
    r.raise_for_status()
    out = r.json()
    if out.get("errors"):
        raise RuntimeError(out["errors"][0].get("message", str(out["errors"])))
    return out["data"]

QUERY = """
query Products($keyword: String, $listType: Int, $sortType: Int, $page: Int, $limit: Int) {
 productOfferV2(keyword:$keyword,listType:$listType,sortType:$sortType,page:$page,limit:$limit) {
  nodes {
   itemId productName productLink offerLink imageUrl priceMin priceMax priceDiscountRate
   sales ratingStar commissionRate sellerCommissionRate shopeeCommissionRate commission
   shopId shopName shopType
  }
  pageInfo { page limit hasNextPage }
 }
}
"""

def n(x):
    try: return float(x or 0)
    except: return 0.0

def pct(x):
    v=n(x)
    return v*100 if v<=1 else v

def score(p):
    sales=max(n(p.get("sales")),0)
    rating=min(max(n(p.get("ratingStar")),0),5)
    comm=max(pct(p.get("commissionRate")),0)
    seller=max(pct(p.get("sellerCommissionRate")),0)
    return round(min(math.log10(sales+1)/5,1)*45 + rating/5*20 +
                 min(comm/20,1)*25 + min(seller/10,1)*10)

def brl(x):
    return f"R$ {n(x):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

st.title("🎯 Caçador de Produtos Shopee")
st.caption("Busca produtos com vendas, boa avaliação e comissão atrativa.")

with st.sidebar:
    st.header("🔎 Filtros")
    keyword=st.text_input("Produto / palavra-chave", placeholder="Ex.: cozinha, vestido")
    ranking=st.selectbox("Ranking",["🔥 Mais vendidos","💰 Maior comissão","🎯 Oportunidade"])
    limit=st.slider("Quantidade",10,100,30,10)
    min_sales=st.number_input("Mínimo de vendas",0,value=0,step=100)
    min_rating=st.slider("Avaliação mínima",0.0,5.0,4.0,0.1)
    min_comm=st.slider("Comissão mínima (%)",0.0,50.0,0.0,0.5)
    go=st.button("🚀 CAÇAR PRODUTOS",type="primary",use_container_width=True)

st.info("💎 A API não informa quantos afiliados divulgam cada produto. A nota de oportunidade usa somente vendas, avaliação e comissão — sem inventar número de afiliados.")

if go:
    sort_type=2 if ranking=="🔥 Mais vendidos" else 5 if ranking=="💰 Maior comissão" else 2
    try:
        with st.spinner("Buscando na Shopee..."):
            data=api(QUERY,{"keyword":keyword.strip() or None,"listType":0,"sortType":sort_type,"page":1,"limit":limit})
        products=data["productOfferV2"]["nodes"] or []
        rows=[]
        for p in products:
            row={"score":score(p),"produto":p.get("productName",""),"loja":p.get("shopName",""),
                 "vendas":int(n(p.get("sales"))),"avaliacao":n(p.get("ratingStar")),
                 "preco":n(p.get("priceMin")),"comissao_pct":pct(p.get("commissionRate")),
                 "comissao_estimada":n(p.get("commission")),"imagem":p.get("imageUrl",""),
                 "link":p.get("offerLink") or p.get("productLink","")}
            if row["vendas"]>=min_sales and row["avaliacao"]>=min_rating and row["comissao_pct"]>=min_comm:
                rows.append(row)
        if ranking=="🎯 Oportunidade":
            rows.sort(key=lambda x:x["score"],reverse=True)
        st.success(f"{len(rows)} produtos encontrados.")
        for i,p in enumerate(rows,1):
            with st.container(border=True):
                c1,c2=st.columns([1,3])
                with c1:
                    if p["imagem"]: st.image(p["imagem"],use_container_width=True)
                with c2:
                    st.subheader(f"#{i} · {p['produto']}")
                    st.write(f"🏪 **{p['loja']}**")
                    a,b,c,d=st.columns(4)
                    a.metric("🎯 Nota",f"{p['score']}/100")
                    b.metric("🛒 Vendas",f"{p['vendas']:,}".replace(",","."))
                    c.metric("⭐ Avaliação",f"{p['avaliacao']:.1f}")
                    d.metric("💰 Comissão",f"{p['comissao_pct']:.1f}%")
                    st.write(f"Preço: **{brl(p['preco'])}** · Comissão estimada: **{brl(p['comissao_estimada'])}**")
                    if p["link"]: st.link_button("🛍️ Abrir link de afiliado",p["link"],use_container_width=True)
        if rows:
            df=pd.DataFrame(rows).drop(columns=["imagem"])
            st.download_button("⬇️ Baixar ranking CSV",df.to_csv(index=False).encode("utf-8-sig"),
                               "ranking_shopee.csv","text/csv",use_container_width=True)
    except Exception as e:
        st.error(f"Erro na consulta: {e}")
else:
    st.markdown("""### Como usar
1. Digite um produto ou deixe vazio.
2. Escolha o ranking.
3. Ajuste os filtros.
4. Toque em **CAÇAR PRODUTOS**.
5. Abra o link de afiliado do produto escolhido.

🔐 O Secret fica privado nos **Secrets do Streamlit** e nunca no código público.
""")
