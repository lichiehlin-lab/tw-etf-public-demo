def validate_batch(batch,repo):
    errors=list(batch.errors); valid=[]
    for price in batch.records:
        etf=repo.get_etf(price.key)
        if not etf:
            errors.append(f'{price.key.code} 名錄身分未確認'); continue
        if etf.currency!=price.currency:
            errors.append(f'{price.key.code} 幣別不一致'); continue
        history=[p for p in repo.prices(price.key) if p.day<price.day]
        previous=history[-1] if history else None
        ratio=1
        if hasattr(repo,'actions') and previous:
            for a in repo.actions(price.key):
                if previous.day<a.effective_date<=price.day: ratio*=a.unit_ratio
        if previous and abs(price.close/(previous.close/ratio)-1)>0.35:
            errors.append(f'{price.key.code} 價格異常跳變，待人工核對'); continue
        valid.append(price)
    return valid,errors
