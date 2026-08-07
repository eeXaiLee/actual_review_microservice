from rest_framework import serializers
from .models import Organization, Branch, Review, Video, Playlist

class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = '__all__'

class BranchSerializer(serializers.ModelSerializer):

    google_review_avg = serializers.DecimalField(max_digits=5, decimal_places=1, coerce_to_string=True, required=False, allow_null=True)
    yandex_review_avg = serializers.DecimalField(max_digits=5, decimal_places=1, coerce_to_string=True, required=False, allow_null=True)
    twogis_review_avg = serializers.DecimalField(max_digits=5, decimal_places=1, coerce_to_string=True, required=False, allow_null=True)
    vlru_review_avg = serializers.DecimalField(max_digits=5, decimal_places=1, coerce_to_string=True, required=False, allow_null=True)

    class Meta:
        model = Branch
        fields = '__all__'


class BranchResponseSerializer(serializers.ModelSerializer):
    """Филиал для ответа API отзывов: организация — вложенным объектом,
    поля провайдеров сгруппированы по названию площадки вместо плоского
    списка из 16 полей с префиксами."""

    organization = OrganizationSerializer(read_only=True)
    providers = serializers.SerializerMethodField()

    class Meta:
        model = Branch
        fields = ['id', 'address', 'organization', 'providers']

    def get_providers(self, branch):
        # review_count/review_avg считаются заранее (см. reviews_query.py) по
        # реальным отзывам в базе, а не берутся из бейджа сайта — так они
        # никогда не разъезжаются с тем, что реально приходит в "reviews"
        provider_stats = self.context.get('provider_stats', {})

        def stats(provider_key):
            return provider_stats.get(provider_key, {
                'review_count': 0,
                'review_avg': None,
                'review_count_filtered': 0,
                'review_avg_filtered': None,
            })

        return {
            'yandex': {
                'url': branch.yandex_map_url,
                'parse_date': branch.yandex_parse_date,
                **stats('yandex'),
            },
            '2gis': {
                'url': branch.twogis_map_url,
                'parse_date': branch.twogis_parse_date,
                **stats('2gis'),
            },
            'vlru': {
                'url': branch.vlru_url,
                'org_id': branch.vlru_org_id,
                'parse_date': branch.vlru_parse_date,
                **stats('vlru'),
            },
        }


class ReviewSerializer(serializers.ModelSerializer):

    rating = serializers.DecimalField(max_digits=5, decimal_places=1, coerce_to_string=True)

    class Meta:
        model = Review
        fields = '__all__'


class ReviewResponseSerializer(serializers.ModelSerializer):
    """Отзыв для ответа API отзывов: photos — настоящий массив URL, а не
    строка через запятую, rating — число, а не строка в кавычках. В БД поля
    не меняются — записью отзывов занимается ReviewSerializer выше, этот
    только читает."""

    rating = serializers.DecimalField(max_digits=5, decimal_places=1, coerce_to_string=False)
    photos = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = '__all__'

    def get_photos(self, review):
        if not review.photos:
            return []
        return [url.strip() for url in review.photos.split(',') if url.strip()]


class VideoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Video
        fields = '__all__'


class PlaylistSerializer(serializers.ModelSerializer):
    class Meta:
        model = Playlist
        fields = '__all__'