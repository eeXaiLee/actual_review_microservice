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
        return {
            'yandex': {
                'url': branch.yandex_map_url,
                'review_count': branch.yandex_review_count,
                'review_avg': branch.yandex_review_avg,
                'parse_date': branch.yandex_parse_date,
            },
            '2gis': {
                'url': branch.twogis_map_url,
                'review_count': branch.twogis_review_count,
                'review_avg': branch.twogis_review_avg,
                'parse_date': branch.twogis_parse_date,
            },
            'vlru': {
                'url': branch.vlru_url,
                'org_id': branch.vlru_org_id,
                'review_count': branch.vlru_review_count,
                'review_avg': branch.vlru_review_avg,
                'parse_date': branch.vlru_parse_date,
            },
        }


class ReviewSerializer(serializers.ModelSerializer):

    rating = serializers.DecimalField(max_digits=5, decimal_places=1, coerce_to_string=True)

    class Meta:
        model = Review
        fields = '__all__'


class VideoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Video
        fields = '__all__'


class PlaylistSerializer(serializers.ModelSerializer):
    class Meta:
        model = Playlist
        fields = '__all__'