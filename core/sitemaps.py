from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from .models import MarketingPage, BlogPost, Video # Assuming Video also needs to be in sitemap

class StaticViewSitemap(Sitemap):
    """Sitemap for static views like homepage, contact, etc. if any."""
    priority = 0.5
    changefreq = 'daily'

    def items(self):
        # Return a list of names of your static views
        # Example: return ['home', 'contact_us', 'about_us']
        # For now, assuming no major static views other than what models provide.
        # If you have a landing page that's not a MarketingPage, add its URL name here.
        return []

    def location(self, item):
        return reverse(item)

class MarketingPageSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8 # Marketing pages are generally important

    def items(self):
        return MarketingPage.objects.filter(status='published').order_by('-published_at')

    def lastmod(self, obj):
        return obj.updated_at # or obj.published_at

    def location(self, obj):
        # Assuming you have a detail view for marketing pages named 'marketingpage-detail'
        # and it takes a 'slug' parameter. This matches the DRF router default.
        # If your frontend has different URL structures, adjust accordingly or use get_absolute_url on model.
        return reverse('marketingpage-detail', kwargs={'slug': obj.slug})


class BlogPostSitemap(Sitemap):
    changefreq = "daily" # Blog posts might update more frequently or new ones added
    priority = 0.7

    def items(self):
        return BlogPost.objects.filter(status='published').order_by('-published_at')

    def lastmod(self, obj):
        return obj.updated_at # or obj.published_at

    def location(self, obj):
        # Assuming a detail view named 'blogpost-detail' taking 'slug'.
        return reverse('blogpost-detail', kwargs={'slug': obj.slug})


class VideoSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.6

    def items(self):
        # Assuming published videos should be in the sitemap
        return Video.objects.filter(status='published').order_by('-uploaded_at')

    def lastmod(self, obj):
        return obj.updated_at # or obj.uploaded_at

    def location(self, obj):
        # Assuming a detail view named 'video-detail' taking 'pk'.
        return reverse('video-detail', kwargs={'pk': obj.pk})

# Dictionary of sitemaps to be used in urls.py
sitemaps = {
    'static': StaticViewSitemap,
    'marketing_pages': MarketingPageSitemap,
    'blog_posts': BlogPostSitemap,
    'videos': VideoSitemap,
}
