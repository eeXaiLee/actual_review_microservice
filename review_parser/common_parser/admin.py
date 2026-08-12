from django.contrib import admin
from django.db.models import Avg, Count, Q
from django.http import HttpResponseRedirect
from django.urls import path, reverse_lazy
from nested_admin import (
    NestedModelAdmin,
    NestedStackedInline,
    NestedTabularInline,
)

from common_parser.tasks import (
    parse_2gis_async,
    parse_all_providers_async,
    parse_vlru_async,
    parse_yandex_async,
    parse_youtube_videos_async,
)

from .models import ApiClient, Branch, Organization, Playlist, Review, Video


class BranchInline(NestedStackedInline):
    model = Branch
    extra = 0
    show_change_link = True

@admin.register(Branch)
class BranchAdmin(NestedModelAdmin):
    list_display = ('id', 'organization', 'address')
    list_filter = ('organization',)

    readonly_fields = (
        'yandex_review_count_computed', 'yandex_review_avg_computed',
        'twogis_review_count_computed', 'twogis_review_avg_computed',
        'vlru_review_count_computed', 'vlru_review_avg_computed',
    )

    fields = (
        'organization', 'address',
        'google_map_url', 'yandex_map_url', 'twogis_map_url', 'vlru_url',
        'google_review_count', 'google_review_avg', 'google_parse_date',
        'yandex_review_count_computed', 'yandex_review_avg_computed', 'yandex_parse_date',
        'twogis_review_count_computed', 'twogis_review_avg_computed', 'twogis_parse_date',
        'vlru_review_count_computed', 'vlru_review_avg_computed', 'vlru_parse_date',
    )

    def _provider_stats(self, obj):
        if not hasattr(obj, '_provider_stats_cache'):
            obj._provider_stats_cache = {
                row["provider"]: row
                for row in obj.reviews.values("provider").annotate(
                    cnt=Count("id"), avg=Avg("rating", filter=Q(rating__gt=0))
                )
            }
        return obj._provider_stats_cache

    def parsing(self, request, object_id=None):

        parse_all_providers_async.delay(object_id)

        return HttpResponseRedirect(reverse_lazy('admin:common_parser_branch_changelist'))

    def parsing_yandex(self, request, object_id=None):

        parse_yandex_async.delay(object_id)
        #branch = get_object_or_404(Branch, id=object_id)
        #create_yandex_reviews(url=branch.yandex_map_url, inn=branch.organization.inn, address=branch.address)

        return HttpResponseRedirect(reverse_lazy('admin:common_parser_branch_changelist'))

    def parsing_2gis(self, request, object_id=None):

        parse_2gis_async.delay(object_id)

        return HttpResponseRedirect(reverse_lazy('admin:common_parser_branch_changelist'))

    def parsing_vlru(self, request, object_id=None):

        parse_vlru_async.delay(object_id)

        return HttpResponseRedirect(reverse_lazy('admin:common_parser_branch_changelist'))

    def get_urls(self):
        urls = super().get_urls()
        info = self.model._meta.app_label, self.model._meta.model_name
        my_urls = [
            path('<path:object_id>/change/parse/', self.admin_site.admin_view(self.parsing)),
            path('<path:object_id>/change/parse-yandex/', self.admin_site.admin_view(self.parsing_yandex)),
            path('<path:object_id>/change/parse-2gis/', self.admin_site.admin_view(self.parsing_2gis)),
            path('<path:object_id>/change/parse-vlru/', self.admin_site.admin_view(self.parsing_vlru)),
        ]
        return my_urls + urls


    change_form_template = 'admin/branch_custom.html'


def _make_provider_metric(provider, metric, label):
    def method(self, obj):
        if not obj.pk:
            return "—"
        row = self._provider_stats(obj).get(provider)
        if metric == "count":
            return row["cnt"] if row else 0
        return round(row["avg"], 2) if row and row["avg"] is not None else "—"
    method.short_description = label
    return method


for provider, field_prefix, label_prefix in (("yandex", "yandex", "Yandex"), ("2gis", "twogis", "Twogis"), ("vlru", "vlru", "Vlru")):
    setattr(BranchAdmin, f"{field_prefix}_review_count_computed", _make_provider_metric(provider, "count", f"{label_prefix} review count"))
    setattr(BranchAdmin, f"{field_prefix}_review_avg_computed", _make_provider_metric(provider, "avg", f"{label_prefix} review avg"))


@admin.register(Organization)
class OrganizationAdmin(NestedModelAdmin):
    list_display = ('id', 'name', 'inn')
    search_fields = ['name']
    ordering = ['id']
    inlines = [BranchInline]



@admin.register(Review)
class ReviewAdmin(NestedModelAdmin):
    list_display = ('id', 'branch', 'author', 'rating', 'published_date')
    list_filter = ('branch', 'rating')
    search_fields = ['author', 'content']
    date_hierarchy = 'published_date'
    ordering = ['-published_date']


@admin.register(ApiClient)
class ApiClientAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'organization')
    autocomplete_fields = ('user', 'organization')


class VideoInline(NestedTabularInline):
    model = Video
    extra = 0
    show_change_link = True


admin.site.register(Video)


@admin.register(Playlist)
class PlaylistAdmin(NestedModelAdmin):
    list_display = ('id', 'title', 'organization', 'count')
    list_filter = ('title',)
    autocomplete_fields = ('organization',)

    inlines = [VideoInline]

    def parsing_youtube(self, request, object_id=None):
        parse_youtube_videos_async.delay(object_id)
        return HttpResponseRedirect(
            reverse_lazy('admin:common_parser_playlist_changelist')
        )

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path(
                '<path:object_id>/change/parse-youtube/',
                self.admin_site.admin_view(self.parsing_youtube)
            ),
        ]
        return my_urls + urls

    change_form_template = 'admin/playlist_custom.html'
