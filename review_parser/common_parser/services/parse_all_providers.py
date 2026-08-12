from loguru import logger

from common_parser.parsers.twogis import create_2gis_reviews
from common_parser.parsers.vlru import create_vlru_reviews
from common_parser.parsers.yandex import create_yandex_reviews


def parse_all_providers(branch):
    success_count = 0
    try_count = 0
    dict_results: dict[str, object] = {}

    try:
        if branch.twogis_map_url:
            try_count += 1
            dict_results["2gis"] = create_2gis_reviews(
                url=branch.twogis_map_url,
                inn=branch.organization.inn,
                address=branch.address,
            )
            if dict_results["2gis"]:
                success_count += 1
    except Exception as e:
        logger.exception(
            f"parse_all_providers: ошибка парсинга 2gis для branch_id={branch.id}: {e}"
        )

    try:
        if branch.vlru_url:
            try_count += 1
            dict_results["vlru"] = create_vlru_reviews(
                branch.vlru_url,
                branch.organization.inn,
                address=branch.address,
            )
            if dict_results["vlru"]:
                success_count += 1
    except Exception as e:
        logger.exception(
            f"parse_all_providers: ошибка парсинга vlru для branch_id={branch.id}: {e}"
        )

    try:
        if branch.yandex_map_url:
            try_count += 1
            dict_results["yandex"] = create_yandex_reviews(
                url=branch.yandex_map_url,
                inn=branch.organization.inn,
                address=branch.address,
            )
            if dict_results["yandex"]:
                success_count += 1
    except Exception as e:
        logger.exception(
            f"parse_all_providers: ошибка парсинга yandex для branch_id={branch.id}: {e}"
        )

    dict_results["tryes"] = try_count
    dict_results["success"] = success_count
    return dict_results
